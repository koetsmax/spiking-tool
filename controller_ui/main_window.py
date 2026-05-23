from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from controller_ui.client_columns import (
    CLIENT_TABLE_COLUMNS,
    configure_client_table,
    populate_client_row,
)
from controller_ui.client_manager import ClientManager
from controller_ui.socket_handlers import register_socket_handlers
from sot.Region import core_regions
from threadedsio import ThreadedSocketClient

_TIP_PORT_SPIKE_REQUIRED = "Enable Port spike first."
_TIP_AUTO_HOLD_BLOCKS_PORT_SPIKE = "Turn off Auto hold to use Port spike."
_TIP_REJOIN_REQUIRES_PORT_SPIKE = "Rejoin session requires Port spike to be enabled."
_TIP_AUTO_SPIKE_BLOCKS_MANUAL = (
    "Disabled while Auto spike mode is running — the controller resets and sails automatically."
)
_TIP_DESIRED_PORT_BLOCKS_MANUAL = (
    "Disabled while Desired port mode is running — the controller resets and sails automatically."
)
_TIP_AUTO_SPIKE_BLOCKS_DESIRED_PORT = "Turn off Auto spike mode to use Desired port mode."
_TIP_DESIRED_PORT_BLOCKS_AUTO_SPIKE = "Turn off Desired port mode to use Auto spike mode."
_TIP_ENTER_PORT = "Enter a port, then click ✓ or click away from the field."
_TIP_ENTER_SHIP_COUNT = "Enter the number of ships, then click ✓ or click away from the field."
_TIP_APPLY_VALUE = "Apply value"


class ControllerWindow(QMainWindow):
    def __init__(self, sio=None):
        super().__init__()
        self.setWindowTitle("Spiking Tool — Controller")
        self.resize(960, 520)
        self.setMinimumSize(720, 400)

        self.sio = sio or ThreadedSocketClient(
            url="http://ashen.spiker.famkoets.nl",
            auth={"name": "Controller", "type": "controller"},
        )
        self.client_manager = ClientManager()
        self.desired_port_mode = False
        self.desired_port = None
        self.auto_hold_mode = False
        self.auto_spike_mode = False
        self.number_of_ships = None
        self.person_to_invite = None
        self._action_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        register_socket_handlers(self)
        self._update_control_states()
        self._update_auto_hold_button()

    def handle_automation_status(self, data: dict) -> None:
        if self.desired_port_mode and self.desired_port is not None:
            client = self.client_manager.get_client(data["client"])
            if isinstance(data["status"], int):
                from spiking_tool.ports import normalize_port_digits

                status = normalize_port_digits(data["status"])
                if int(status) != int(self.desired_port.strip()):
                    print(f"C{client.name}: {int(status)}")
                    self.emit_client_event("reset", client.name)
                else:
                    print(f"----------------------MATCH FOUND: {client.name}----------------------")
                    self.desired_port_mode = False
                    self.desired_port = None
                    self.desired_port_mode_checkbox.setChecked(False)
                    self._update_control_states()
            elif data["status"] == "Ready":
                self.emit_client_event("sail", client.name)

        elif self.auto_spike_mode and self.number_of_ships is not None:
            all_clients_matched = True
            all_client_ready = True
            for client in self.client_manager.clients.values():
                if client.port is None:
                    all_clients_matched = False
                if client.status != "Ready":
                    all_client_ready = False
            if all_clients_matched:
                for client in self.client_manager.clients.values():
                    if self.client_manager.biggest_match >= int(self.number_of_ships):
                        print(
                            f"----------------------MATCH OF {self.number_of_ships} "
                            f"FOUND WITH {self.client_manager.biggest_match} SHIPS----------------------"
                        )
                    else:
                        print(
                            f"no match of {self.number_of_ships} found. "
                            f"Biggest match was {self.client_manager.biggest_match} ships"
                        )
                        self.emit_client_event("reset", client.name)
            if all_client_ready:
                self.emit_client_event("sail")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_manual_tab(), "Manual")
        tabs.addTab(self._build_automated_tab(), "Automated")
        tabs.addTab(self._build_debug_tab(), "Debug")
        tabs.setMinimumWidth(320)
        splitter.addWidget(tabs)

        clients_panel = QFrame()
        clients_panel.setObjectName("clientsPanel")
        clients_layout = QVBoxLayout(clients_panel)
        clients_layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Clients")
        title.setObjectName("sectionTitle")
        clients_layout.addWidget(title)

        self.biggest_match_label = QLabel("No matches found")
        self.biggest_match_label.setObjectName("biggestMatch")
        self.biggest_match_label.setWordWrap(True)
        clients_layout.addWidget(self.biggest_match_label)

        self.client_table = QTableWidget(0, len(CLIENT_TABLE_COLUMNS))
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.setShowGrid(False)
        self.client_table.setSelectionMode(QTableWidget.NoSelection)
        self.client_table.setFocusPolicy(Qt.NoFocus)
        self.client_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.client_table.setAlternatingRowColors(True)
        configure_client_table(self.client_table)
        clients_layout.addWidget(self.client_table, stretch=1)

        splitter.addWidget(clients_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 520])

    def _centered_cell_widget(self, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addStretch()
        layout.addWidget(widget, 0, Qt.AlignCenter)
        layout.addStretch()
        return container

    def _build_manual_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Region"))
        self.region_combo = QComboBox()
        self.region_combo.addItems(list(core_regions.keys()))
        self.region_combo.setCurrentText("US East - Washington")
        self.region_combo.currentTextChanged.connect(self.change_region)
        layout.addWidget(self.region_combo)

        self.portspike_checkbox = QCheckBox("Port spike")
        self.portspike_checkbox.toggled.connect(self.set_port_spike)
        layout.addWidget(self.portspike_checkbox)

        layout.addWidget(self._section_label("Actions"))
        for text, event in (
            ("Launch game", "launch_game"),
            ("Sail", "sail"),
            ("Rejoin session", "rejoin_session"),
            ("Reset", "reset"),
            ("Kill game", "kill_game"),
            ("Stop running functions", "stop_functions"),
        ):
            button = self._add_action_button(
                layout,
                text,
                event,
                lambda checked=False, e=event: self.emit_client_event(e),
            )
            if event == "rejoin_session":
                self.rejoin_session_button = button

        layout.addStretch()
        return tab

    def _build_automated_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("Desired port"))
        self.desired_port_mode_checkbox = QCheckBox("Desired port mode")
        self.desired_port_mode_checkbox.toggled.connect(self.set_desired_port_mode)
        layout.addWidget(self.desired_port_mode_checkbox)

        self.desired_port_entry, self.desired_port_confirm, desired_port_row = (
            self._build_entry_with_confirm("Port (e.g. 042)", self.set_desired_port)
        )
        layout.addWidget(desired_port_row)

        layout.addWidget(self._section_label("Auto spike"))
        self.auto_spike_mode_checkbox = QCheckBox("Auto spike mode")
        self.auto_spike_mode_checkbox.toggled.connect(self.set_auto_spike_mode)
        layout.addWidget(self.auto_spike_mode_checkbox)

        self.number_of_ships_entry, self.number_of_ships_confirm, ships_row = (
            self._build_entry_with_confirm("Number of ships", self.set_number_of_ships)
        )
        layout.addWidget(ships_row)

        layout.addWidget(self._section_label("Auto hold"))
        self.auto_hold_button = QPushButton("Toggle auto hold")
        self.auto_hold_button.setObjectName("autoHoldToggleButton")
        self.auto_hold_button.setProperty("autoHoldActive", False)
        self.auto_hold_button.setProperty("lastPressed", False)
        self.auto_hold_button.clicked.connect(self.toggle_auto_hold)
        self._action_buttons["auto_hold"] = self.auto_hold_button
        layout.addWidget(self.auto_hold_button)

        layout.addStretch()
        return tab

    def _build_debug_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("Last action"))
        self.last_pressed_label = QLabel("Last pressed: None")
        self.last_pressed_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.last_pressed_label)

        layout.addWidget(self._section_label("Display"))
        self._add_action_button(
            layout,
            "Fix game resolution (800x600)",
            "fix_resolution",
            lambda: self.emit_client_event("fix_resolution"),
        )

        layout.addWidget(self._section_label("Match"))
        self._add_action_button(
            layout,
            "Forget last match",
            "forget_match",
            lambda: self.emit_client_event("forget_match"),
        )

        layout.addWidget(self._section_label("Hold"))
        self._add_action_button(
            layout, "Simulate hold request", "hold_request", self.start_hold_request
        )

        layout.addWidget(self._section_label("Invite"))
        self.person_to_invite_entry = QLineEdit("person_to_invite")
        self.person_to_invite_entry.returnPressed.connect(self.set_person_to_invite)
        layout.addWidget(self.person_to_invite_entry)

        self._add_action_button(
            layout, "Simulate invite request", "invite_request", self.emit_invite_request
        )

        layout.addStretch()
        return tab

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _build_entry_with_confirm(
        self, placeholder: str, on_confirm
    ) -> tuple[QLineEdit, QPushButton, QWidget]:
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        confirm = QPushButton("✓")
        confirm.setObjectName("entryConfirmButton")
        confirm.setToolTip(_TIP_APPLY_VALUE)
        entry.editingFinished.connect(on_confirm)
        confirm.clicked.connect(entry.clearFocus)
        entry.returnPressed.connect(entry.clearFocus)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(entry, stretch=1)
        row_layout.addWidget(confirm)
        return entry, confirm, row

    @staticmethod
    def _apply_entry_row(
        entry: QLineEdit, confirm: QPushButton, enabled: bool, disabled_tooltip: str
    ) -> None:
        ControllerWindow._apply_control(entry, enabled, disabled_tooltip)
        ControllerWindow._apply_control(
            confirm, enabled, disabled_tooltip if not enabled else _TIP_APPLY_VALUE
        )

    def _add_action_button(
        self, layout: QVBoxLayout, text: str, event_key: str, callback
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("lastPressed", False)
        button.clicked.connect(callback)
        self._action_buttons[event_key] = button
        layout.addWidget(button)
        return button

    def _set_last_pressed(self, event_key: str, display_name: str | None = None) -> None:
        label = display_name or event_key.replace("_", " ").title()
        self.last_pressed_label.setText(f"Last pressed: {label}")

        for key, button in self._action_buttons.items():
            is_last = key == event_key
            if button.property("lastPressed") == is_last:
                continue
            button.setProperty("lastPressed", is_last)
            button.style().unpolish(button)
            button.style().polish(button)

    def _port_spike_controls_enabled(self) -> bool:
        return self.portspike_checkbox.isChecked() and not self.auto_hold_mode

    @staticmethod
    def _apply_control(widget, enabled: bool, disabled_tooltip: str = "") -> None:
        widget.setEnabled(enabled)
        widget.setToolTip("" if enabled else disabled_tooltip)

    def _update_control_states(self) -> None:
        port_spike_on = self._port_spike_controls_enabled()
        automation_active = self.auto_spike_mode or self.desired_port_mode

        self._apply_control(
            self.portspike_checkbox,
            not self.auto_hold_mode,
            _TIP_AUTO_HOLD_BLOCKS_PORT_SPIKE,
        )

        self._apply_control(
            self.rejoin_session_button,
            port_spike_on and not self.auto_spike_mode,
            _TIP_AUTO_SPIKE_BLOCKS_MANUAL
            if self.auto_spike_mode
            else _TIP_REJOIN_REQUIRES_PORT_SPIKE,
        )

        self._apply_control(
            self.desired_port_mode_checkbox,
            port_spike_on and not self.auto_spike_mode,
            _TIP_AUTO_SPIKE_BLOCKS_DESIRED_PORT
            if self.auto_spike_mode
            else _TIP_PORT_SPIKE_REQUIRED,
        )

        self._apply_control(
            self.auto_spike_mode_checkbox,
            port_spike_on and not self.desired_port_mode,
            _TIP_DESIRED_PORT_BLOCKS_AUTO_SPIKE
            if self.desired_port_mode
            else _TIP_PORT_SPIKE_REQUIRED,
        )

        desired_port_entry_on = (
            port_spike_on and self.desired_port_mode and not self.auto_spike_mode
        )
        desired_port_tip = (
            _TIP_AUTO_SPIKE_BLOCKS_DESIRED_PORT
            if self.auto_spike_mode
            else _TIP_PORT_SPIKE_REQUIRED
            if not port_spike_on
            else _TIP_ENTER_PORT
        )
        self._apply_entry_row(
            self.desired_port_entry,
            self.desired_port_confirm,
            desired_port_entry_on,
            desired_port_tip,
        )

        ships_entry_on = (
            port_spike_on and self.auto_spike_mode and not self.desired_port_mode
        )
        ships_tip = (
            _TIP_DESIRED_PORT_BLOCKS_AUTO_SPIKE
            if self.desired_port_mode
            else _TIP_PORT_SPIKE_REQUIRED
            if not port_spike_on
            else _TIP_ENTER_SHIP_COUNT
        )
        self._apply_entry_row(
            self.number_of_ships_entry,
            self.number_of_ships_confirm,
            ships_entry_on,
            ships_tip,
        )

        manual_disabled_tip = (
            _TIP_AUTO_SPIKE_BLOCKS_MANUAL
            if self.auto_spike_mode
            else _TIP_DESIRED_PORT_BLOCKS_MANUAL
        )
        for event in ("sail", "reset"):
            button = self._action_buttons.get(event)
            if button:
                self._apply_control(
                    button,
                    not automation_active,
                    manual_disabled_tip,
                )

    def _update_auto_hold_button(self) -> None:
        self.auto_hold_button.setProperty("autoHoldActive", self.auto_hold_mode)
        self.auto_hold_button.style().unpolish(self.auto_hold_button)
        self.auto_hold_button.style().polish(self.auto_hold_button)

    def toggle_auto_hold(self) -> None:
        self._set_auto_hold_mode(not self.auto_hold_mode, notify_clients=True)
        self._set_last_pressed("auto_hold", "Toggle auto hold")

    def _set_auto_hold_mode(self, enabled: bool, *, notify_clients: bool = True) -> None:
        self.auto_hold_mode = enabled

        if enabled:
            self.portspike_checkbox.blockSignals(True)
            self.portspike_checkbox.setChecked(False)
            self.portspike_checkbox.blockSignals(False)
            self.sio.emit("portspiking", False)
            self.desired_port_mode_checkbox.setChecked(False)
            self.auto_spike_mode_checkbox.setChecked(False)
            self.desired_port_mode = False
            self.auto_spike_mode = False
            self.desired_port_entry.clear()
            self.number_of_ships_entry.clear()

        self._update_auto_hold_button()
        self._update_control_states()

        if notify_clients:
            active_clients = self.client_manager.get_active_clients()
            self.sio.emit("client_event", {"event": "auto_hold", "clients": active_clients})

    def change_region(self, *_args):
        self.sio.emit("region", self.region_combo.currentText())

    def set_port_spike(self, *_args):
        if self.portspike_checkbox.isChecked():
            if self.auto_hold_mode:
                self._set_auto_hold_mode(False, notify_clients=False)
        else:
            self.desired_port_mode_checkbox.setChecked(False)
            self.auto_spike_mode_checkbox.setChecked(False)
            self.desired_port_mode = False
            self.auto_spike_mode = False
        self.sio.emit("portspiking", self.portspike_checkbox.isChecked())
        self._update_control_states()

    def set_desired_port_mode(self, checked=None):
        self.desired_port_mode = self.desired_port_mode_checkbox.isChecked()
        if self.desired_port_mode and self.auto_spike_mode:
            self.auto_spike_mode_checkbox.setChecked(False)
            self.auto_spike_mode = False
            self.number_of_ships_entry.clear()
        print(f"Desired port mode set to {self.desired_port_mode}")
        self._update_control_states()

    def set_desired_port(self, *_args):
        port = self.desired_port_entry.text().strip()
        if not port:
            return
        self.desired_port = port
        print(f"Desired port set to {self.desired_port}")

    def set_auto_spike_mode(self, checked=None):
        self.auto_spike_mode = self.auto_spike_mode_checkbox.isChecked()
        if self.auto_spike_mode and self.desired_port_mode:
            self.desired_port_mode_checkbox.setChecked(False)
            self.desired_port_mode = False
            self.desired_port_entry.clear()
        print(f"Auto spike mode set to {self.auto_spike_mode}")
        self._update_control_states()

    def set_number_of_ships(self, *_args):
        ships = self.number_of_ships_entry.text().strip()
        if not ships:
            return
        self.number_of_ships = ships
        print(f"Number of ships set to {self.number_of_ships}")

    def set_person_to_invite(self, *_args):
        self.person_to_invite = self.person_to_invite_entry.text()
        print(f"Person to invite set to {self.person_to_invite}")

    def emit_client_event(self, event, *args):
        self._set_last_pressed(event)
        active_clients = list(args) if args else self.client_manager.get_active_clients()
        self.sio.emit("client_event", {"event": event, "clients": active_clients})
        if event == "reset":
            self.client_manager.reset_clients()
        if event == "forget_match":
            for client_name in active_clients:
                client = self.client_manager.get_client(client_name)
                if client:
                    client.port = None
                    client.status = "Pending..."
                    if client.status_label:
                        client.status_label.setText(client.status)
            self.client_manager.update_biggest_match(self.biggest_match_label)

    def start_hold_request(self):
        active_clients = self.client_manager.get_active_clients()
        client = None
        for client_name in active_clients:
            client = self.client_manager.get_client(client_name)
            if client.holding:
                print(f"{client.name} is already holding")
                continue
            print(f"{client.name} is not holding")
            break
        if client:
            self.emit_client_event("hold_request", client.name)

    def emit_invite_request(self, *_args):
        active_clients = self.client_manager.get_active_clients()
        if not active_clients:
            print("No active clients selected for invite request")
            return
        self._set_last_pressed("invite_request")
        target_client = active_clients[0]
        self.person_to_invite = self.person_to_invite_entry.text()
        self.sio.emit(
            "invite_request",
            {"person_to_invite": self.person_to_invite, "clients": target_client},
        )

    def sort_client_list(self):
        self.client_manager.sort_clients_by_name()
        self.create_client_list()

    def create_client_list(self):
        self.client_table.setRowCount(0)
        name_column_index = next(
            i for i, col in enumerate(CLIENT_TABLE_COLUMNS) if col.column_id == "name"
        )

        for client_name in self.client_manager.clients:
            client = self.client_manager.get_client(client_name)
            row = self.client_table.rowCount()
            self.client_table.insertRow(row)
            client.column_widgets = {}
            populate_client_row(self.client_table, row, client, self)

        self.client_table.resizeColumnToContents(name_column_index)


# Backward-compatible alias
Controller = ControllerWindow
