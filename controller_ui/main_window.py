from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from controller_ui.client_manager import ClientManager
from controller_ui.socket_handlers import register_socket_handlers
from sot.Region import core_regions
from threadedsio import ThreadedSocketClient


class ControllerWindow(QMainWindow):
    def __init__(self, sio=None):
        super().__init__()
        self.setWindowTitle("Spiking Tool — Controller")
        self.resize(960, 520)
        self.setMinimumSize(720, 400)

        self.sio = sio or ThreadedSocketClient(
            url="http://ashen.spiker.famkoets.nl", auth="Controller"
        )
        self.client_manager = ClientManager()
        self.desired_port_mode = False
        self.desired_port = None
        self.auto_hold_mode = False
        self.auto_spike_mode = False
        self.number_of_ships = None
        self.person_to_invite = None

        self._build_ui()
        register_socket_handlers(self)

    def handle_automation_status(self, data: dict) -> None:
        if self.desired_port_mode and self.desired_port is not None:
            client = self.client_manager.get_client(data["client"])
            if isinstance(data["status"], int):
                status = int(str(data["status"])[2:])
                if len(str(status).strip()) < 3:
                    status = "0" * (3 - len(str(status))) + str(status)
                if int(status) != int(self.desired_port.strip()):
                    print(f"C{client.name}: {int(status)}")
                    self.emit_client_event("reset", client.name)
                else:
                    print(f"----------------------MATCH FOUND: {client.name}----------------------")
                    self.desired_port_mode = False
                    self.desired_port = None
                    self.desired_port_mode_checkbox.setChecked(False)
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

        self.client_table = QTableWidget(0, 4)
        self.client_table.setHorizontalHeaderLabels(["Active", "Instance", "Ship", "Status"])
        self.client_table.verticalHeader().setVisible(False)
        self.client_table.setShowGrid(False)
        self.client_table.setSelectionMode(QTableWidget.NoSelection)
        self.client_table.setFocusPolicy(Qt.NoFocus)
        self.client_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.client_table.setAlternatingRowColors(True)
        self._configure_client_table()
        clients_layout.addWidget(self.client_table, stretch=1)

        splitter.addWidget(clients_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 520])

    def _configure_client_table(self):
        header = self.client_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.client_table.setColumnWidth(0, 56)
        self.client_table.verticalHeader().setDefaultSectionSize(40)

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
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked=False, e=event: self.emit_client_event(e))
            layout.addWidget(btn)

        self.last_pressed_label = QLabel("Last pressed: None")
        self.last_pressed_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.last_pressed_label)
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

        self.desired_port_entry = QLineEdit()
        self.desired_port_entry.setPlaceholderText("Port (e.g. 042)")
        self.desired_port_entry.returnPressed.connect(self.set_desired_port)
        layout.addWidget(self.desired_port_entry)

        layout.addWidget(self._section_label("Auto spike"))
        self.auto_spike_mode_checkbox = QCheckBox("Auto spike mode")
        self.auto_spike_mode_checkbox.toggled.connect(self.set_auto_spike_mode)
        layout.addWidget(self.auto_spike_mode_checkbox)

        self.number_of_ships_entry = QLineEdit()
        self.number_of_ships_entry.setPlaceholderText("Number of ships")
        self.number_of_ships_entry.returnPressed.connect(self.set_number_of_ships)
        layout.addWidget(self.number_of_ships_entry)

        layout.addWidget(self._section_label("Auto hold"))
        auto_hold_btn = QPushButton("Start auto hold function")
        auto_hold_btn.clicked.connect(lambda: self.emit_client_event("auto_hold"))
        layout.addWidget(auto_hold_btn)

        self.auto_hold_label = QLabel("Auto hold: False")
        layout.addWidget(self.auto_hold_label)

        layout.addStretch()
        return tab

    def _build_debug_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("Match"))
        forget_match_btn = QPushButton("Forget last match")
        forget_match_btn.clicked.connect(lambda: self.emit_client_event("forget_match"))
        layout.addWidget(forget_match_btn)

        layout.addWidget(self._section_label("Hold"))
        hold_btn = QPushButton("Simulate hold request")
        hold_btn.clicked.connect(self.start_hold_request)
        layout.addWidget(hold_btn)

        layout.addWidget(self._section_label("Invite"))
        self.person_to_invite_entry = QLineEdit("person_to_invite")
        self.person_to_invite_entry.returnPressed.connect(self.set_person_to_invite)
        layout.addWidget(self.person_to_invite_entry)

        invite_btn = QPushButton("Simulate invite request")
        invite_btn.clicked.connect(self.emit_invite_request)
        layout.addWidget(invite_btn)

        layout.addStretch()
        return tab

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def change_region(self, *_args):
        self.sio.emit("region", self.region_combo.currentText())

    def set_port_spike(self, *_args):
        self.sio.emit("portspiking", self.portspike_checkbox.isChecked())

    def set_desired_port_mode(self, checked=None):
        self.desired_port_mode = self.desired_port_mode_checkbox.isChecked()
        print(f"Desired port mode set to {self.desired_port_mode}")

    def set_desired_port(self, *_args):
        self.desired_port = self.desired_port_entry.text()
        print(f"Desired port set to {self.desired_port}")

    def set_auto_spike_mode(self, checked=None):
        self.auto_spike_mode = self.auto_spike_mode_checkbox.isChecked()
        print(f"Auto spike mode set to {self.auto_spike_mode}")

    def set_number_of_ships(self, *_args):
        self.number_of_ships = self.number_of_ships_entry.text()
        print(f"Number of ships set to {self.number_of_ships}")

    def set_person_to_invite(self, *_args):
        self.person_to_invite = self.person_to_invite_entry.text()
        print(f"Person to invite set to {self.person_to_invite}")

    def emit_client_event(self, event, *args):
        self.last_pressed_label.setText(f"Last pressed: {event}")
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
        if event == "auto_hold":
            self.auto_hold_mode = not self.auto_hold_mode
            self.auto_hold_label.setText(f"Auto hold: {self.auto_hold_mode}")
            if self.auto_hold_mode:
                self.portspike_checkbox.setChecked(False)
                self.desired_port_mode_checkbox.setChecked(False)
                self.auto_spike_mode_checkbox.setChecked(False)
                self.desired_port_entry.clear()
                self.number_of_ships_entry.clear()

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
        client = "sot1"
        self.person_to_invite = self.person_to_invite_entry.text()
        self.sio.emit(
            "invite_request",
            {"person_to_invite": self.person_to_invite, "clients": client},
        )

    def sort_client_list(self):
        self.client_manager.sort_clients_by_name()
        self.create_client_list()

    def create_client_list(self):
        self.client_table.setRowCount(0)
        ship_types = ["Sloop", "Brigantine", "Galleon", "Captaincy"]

        for client_name in self.client_manager.clients:
            client = self.client_manager.get_client(client_name)
            row = self.client_table.rowCount()
            self.client_table.insertRow(row)

            was_checked = (
                client.active_checkbox.isChecked() if client.active_checkbox else True
            )
            ship_type = client.ship_combo.currentText() if client.ship_combo else client.ship_type
            status = client.status

            active_checkbox = QCheckBox()
            active_checkbox.setChecked(was_checked)
            client.active_checkbox = active_checkbox
            self.client_table.setCellWidget(row, 0, self._centered_cell_widget(active_checkbox))

            name_item = QTableWidgetItem(client.name)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.client_table.setItem(row, 1, name_item)

            ship_combo = QComboBox()
            ship_combo.addItems(ship_types)
            ship_combo.setCurrentText(ship_type)
            ship_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            client.ship_combo = ship_combo

            def ship_type_changed(text, c=client):
                c.ship_type = text
                self.sio.emit(
                    "change_ship",
                    data={"client": c.name, "ship_type": text},
                )

            ship_combo.currentTextChanged.connect(ship_type_changed)
            self.client_table.setCellWidget(row, 2, ship_combo)

            status_label = QLabel(status)
            status_label.setWordWrap(True)
            status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            client.status_label = status_label
            status_container = QWidget()
            status_layout = QHBoxLayout(status_container)
            status_layout.setContentsMargins(8, 0, 4, 0)
            status_layout.addWidget(status_label, 1)
            self.client_table.setCellWidget(row, 3, status_container)

        self.client_table.resizeColumnToContents(1)


# Backward-compatible alias
Controller = ControllerWindow
