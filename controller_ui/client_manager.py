from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import time

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QCheckBox, QComboBox, QPushButton, QWidget

    from controller_ui.client_columns import MetricState
    from spiking_tool.match import MatchDetails


_REJOIN_COPYABLE_STATUSES = frozenset(
    {
        "Rejoining session",
        "Awaiting rejoin prompt",
        "Awaiting connection",
    }
)


def _status_keeps_match_copyable(status, match) -> bool:
    if match is not None:
        return True
    if isinstance(status, int):
        return True
    if isinstance(status, str):
        if status in _REJOIN_COPYABLE_STATUSES:
            return True
        if status.startswith("Rejoining "):
            return True
        if status.startswith("Loading") or " - Loading" in status:
            return True
        if status.startswith("Loaded") or " - Loaded" in status:
            return True
        if status == "Waiting to load" or status.endswith(" - Waiting to load"):
            return True
    return False


def _status_clears_all_match_state(status) -> bool:
    if not isinstance(status, str):
        return False
    if status in (
        "Pending...",
        "Searching the seas",
        "Leaving Game",
        "Ready",
        "Starting Game",
        "Waiting for start screen",
        "Selecting gamemode",
        "Selecting ship",
        "Confirming crew",
    ):
        return True
    if status == "Waiting to load" or status.endswith(" - Waiting to load"):
        return True
    return False


def _status_clears_stale_port(status) -> bool:
    if not isinstance(status, str):
        return False
    if status.startswith("Loading") or " - Loading" in status:
        return True
    if status.startswith("Loaded") or " - Loaded" in status:
        return True
    return False


def _status_confirms_port(status, match) -> bool:
    if match is not None:
        return True
    return isinstance(status, int)


_DEBUG_MATCH_PAYLOAD = {
    "game_ip": "0.0.0.0",
    "game_port": 30700,
    "management_ip": "0.0.0.0",
    "management_port": 40555,
    "region": "US East - Washington DC (NY)",
}


class Client:
    def __init__(self, name: str) -> None:
        self.name = name
        self.simulated = False
        self.ship_type = "Brigantine"
        self.status = "Pending..."
        self.metrics: dict[str, "MetricState"] = {}
        self.column_widgets: dict[str, "QWidget"] = {}
        self.active_checkbox: Optional[QCheckBox] = None
        self.name_label: Optional[QLabel] = None
        self.ship_combo: Optional[QComboBox] = None
        self.status_label: Optional[QLabel] = None
        self.port: Optional[str] = None
        self.match: Optional["MatchDetails"] = None
        self.last_match: Optional["MatchDetails"] = None
        self.afk_enabled = False
        self.afk_status = ""
        self.afk_toggle_button: Optional["QPushButton"] = None
        self.afk_status_label: Optional[QLabel] = None
        self.afk_countdown_deadline: Optional[float] = None
        self.afk_countdown_payload: Optional["AfkStatusPayload"] = None
        self.afk_last_payload: Optional["AfkStatusPayload"] = None
        self.afk_show_status = False


class ClientManager:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.biggest_match: Optional[int] = None

    def add_client(self, name: str) -> None:
        self.clients[name] = Client(name)

    def add_simulated_client(self) -> str:
        index = 1
        while True:
            name = f"Sim-{index}"
            if name not in self.clients:
                break
            index += 1
        client = Client(name)
        client.simulated = True
        client.active_checkbox = None
        self.clients[name] = client
        return name

    def match_group_size_for(self, client: Client) -> int | None:
        if client.match is None:
            return None
        port = client.match.management_port_digits
        return sum(1 for other in self.clients.values() if other.match is not None and other.match.management_port_digits == port)

    def refresh_all_name_holos(self) -> None:
        from controller_ui.client_columns import refresh_client_name_holo

        for client in self.clients.values():
            refresh_client_name_holo(client, self)

    def apply_debug_match_simulation(self, size: int) -> list[str]:
        targets = self._clients_for_debug_match(size)
        payload = _DEBUG_MATCH_PAYLOAD
        status = payload["management_port"]
        for name in list(self.clients.keys()):
            if name == "Controller":
                continue
            if name in targets:
                self.set_client_status(
                    name,
                    status,
                    match=payload,
                    selected_region=None,
                )
            elif self.clients[name].match is not None:
                self.clients[name].match = None
                self.clients[name].last_match = None
                self.clients[name].port = None
                self.clients[name].status = "Pending..."
                if self.clients[name].status_label:
                    self.clients[name].status_label.setText("Pending...")
                    from controller_ui.client_columns import ClickableStatusLabel

                    if isinstance(self.clients[name].status_label, ClickableStatusLabel):
                        self.clients[name].status_label.update_match_style()
        return targets

    def clear_debug_simulation(self) -> None:
        self.reset_clients()
        for name in list(self.clients.keys()):
            if self.clients[name].simulated:
                self.remove_client(name)

    def _clients_for_debug_match(self, size: int) -> list[str]:
        names = [name for name in self.clients if name != "Controller"]
        while len(names) < size:
            names.append(self.add_simulated_client())

        active = set(self.get_active_clients())
        ordered: list[str] = [name for name in names if name in active]
        ordered.extend(name for name in names if name not in active)
        return ordered[:size]

    def get_active_clients(self) -> list[str]:
        return [name for name, client in self.clients.items() if client.active_checkbox and client.active_checkbox.isChecked()]

    def get_client(self, name: str) -> Optional[Client]:
        return self.clients.get(name)

    def set_client_status(
        self,
        name: str,
        status,
        match=None,
        *,
        selected_region: str | None = None,
    ) -> None:
        from controller_ui.client_columns import ClickableStatusLabel
        from spiking_tool.match import MatchDetails
        from spiking_tool.region_match import match_in_selected_region
        from spiking_tool.ports import format_client_status

        client = self.get_client(name)
        if not client:
            return

        if _status_clears_all_match_state(status):
            client.match = None
            client.last_match = None
            client.port = None
        elif _status_clears_stale_port(status):
            client.port = None
            client.last_match = None

        if match is not None:
            client.match = MatchDetails.from_payload(match)
            client.last_match = client.match
        elif _status_keeps_match_copyable(status, match):
            if client.match is None and client.last_match is not None and client.port is not None:
                client.match = client.last_match
        else:
            client.match = None

        display_status, port = format_client_status(status, client.port, current_status=client.status)
        if _status_confirms_port(status, match) and port is not None:
            client.port = port

        match_for_region = client.match or client.last_match
        if port is not None and selected_region and match_for_region is not None and not match_in_selected_region(match_for_region, selected_region):
            if isinstance(status, int):
                display_status = f"{port} - wrong region"
            else:
                display_status = f"{port} - {display_status}"

        client.status = display_status
        if client.status_label:
            client.status_label.setText(str(client.status))
            if isinstance(client.status_label, ClickableStatusLabel):
                client.status_label.update_match_style()

    def set_client_metric(self, name: str, metric: str, state: "MetricState") -> None:
        from controller_ui.client_columns import refresh_client_metrics

        client = self.get_client(name)
        if not client:
            return
        client.metrics[metric] = state
        refresh_client_metrics(client)

    def _clear_client_afk_countdown(self, client: Client) -> None:
        client.afk_countdown_deadline = None
        client.afk_countdown_payload = None

    def _render_client_afk_status(self, client: Client, *, remaining: int | None = None) -> None:
        if not client.afk_status_label:
            return
        payload = client.afk_countdown_payload or client.afk_last_payload
        if client.afk_countdown_payload and client.afk_countdown_payload.type == "countdown":
            if remaining is None and client.afk_countdown_deadline is not None:
                remaining = int(client.afk_countdown_deadline - time.monotonic())
            text = client.afk_countdown_payload.display_text(remaining_seconds=remaining or 0)
        else:
            text = client.afk_status
        client.afk_status_label.setText(text)
        tooltip = payload.tooltip() if payload else ""
        client.afk_status_label.setToolTip(tooltip)

    def set_client_afk_status(self, name: str, status) -> None:
        from spiking_tool.afk_status import AfkStatusPayload

        client = self.get_client(name)
        if not client:
            return

        payload = AfkStatusPayload.from_payload(status)
        if payload is None:
            return

        if payload.type == "clear":
            self._clear_client_afk_countdown(client)
            client.afk_last_payload = None
            client.afk_status = ""
            client.afk_show_status = False
            self._render_client_afk_status(client)
            return

        client.afk_last_payload = payload
        if payload.type == "countdown":
            client.afk_countdown_payload = payload
            client.afk_countdown_deadline = time.monotonic() + payload.seconds
            client.afk_status = payload.display_text(remaining_seconds=payload.seconds)
        else:
            self._clear_client_afk_countdown(client)
            client.afk_status = payload.display_text()
            if payload.type == "error":
                client.afk_show_status = True
                if client.afk_status_label:
                    client.afk_status_label.setStyleSheet("color: #f38ba8;")
            elif client.afk_status_label:
                client.afk_status_label.setStyleSheet("")

        self._render_client_afk_status(
            client,
            remaining=payload.seconds if payload.type == "countdown" else None,
        )

    def tick_afk_countdowns(self) -> None:
        for client in self.clients.values():
            if client.afk_countdown_deadline is None or client.afk_countdown_payload is None:
                continue
            remaining = int(client.afk_countdown_deadline - time.monotonic())
            client.afk_status = client.afk_countdown_payload.display_text(remaining_seconds=remaining)
            self._render_client_afk_status(client, remaining=remaining)

    def set_client_afk_enabled(
        self,
        name: str,
        enabled: bool,
        *,
        preserve_status: bool = False,
    ) -> None:
        from controller_ui.client_columns import style_afk_toggle_button

        client = self.get_client(name)
        if not client:
            return
        client.afk_enabled = enabled
        if enabled and not preserve_status:
            client.afk_show_status = False
            self._clear_client_afk_countdown(client)
            client.afk_last_payload = None
            client.afk_status = ""
            if client.afk_status_label:
                client.afk_status_label.setText("")
                client.afk_status_label.setToolTip("")
                client.afk_status_label.setStyleSheet("")
        elif not enabled and not preserve_status:
            client.afk_show_status = False
            self._clear_client_afk_countdown(client)
            client.afk_last_payload = None
            client.afk_status = ""
            if client.afk_status_label:
                client.afk_status_label.setText("")
                client.afk_status_label.setToolTip("")
                client.afk_status_label.setStyleSheet("")
        if client.afk_toggle_button:
            style_afk_toggle_button(client.afk_toggle_button, enabled)

    def remove_client(self, name: str) -> None:
        if name in self.clients:
            del self.clients[name]

    def update_biggest_match(self, label: QLabel) -> None:
        port_counts: dict[str, list[str]] = {}
        for client_name, client in self.clients.items():
            if client.match is None:
                continue
            port = client.match.management_port_digits
            port_counts.setdefault(port, []).append(client_name)

        biggest_match = None
        for port, clients in port_counts.items():
            if biggest_match is None or len(clients) > len(port_counts[biggest_match]):
                biggest_match = port

        if biggest_match:
            matching_clients = ", ".join(port_counts[biggest_match])
            num_matching_clients = len(port_counts[biggest_match])
            label.setText(f"Biggest match: {num_matching_clients} on port {biggest_match} " f"({matching_clients})")
            self.biggest_match = num_matching_clients
        else:
            label.setText("No matches found")
            self.biggest_match = None
        self.refresh_all_name_holos()

    def reset_clients(self) -> None:
        from controller_ui.client_columns import ClickableStatusLabel

        for client in self.clients.values():
            client.port = None
            client.match = None
            client.last_match = None
            if client.status_label and isinstance(client.status_label, ClickableStatusLabel):
                client.status_label.update_match_style()
        self.refresh_all_name_holos()

    def get_biggest_match(self) -> Optional[int]:
        return self.biggest_match

    def sort_clients_by_name(self) -> None:
        from spiking_tool.client_identity import sort_display_name_key

        self.clients = dict(sorted(self.clients.items(), key=lambda item: sort_display_name_key(item[0])))

    def sync_client_roster(self, display_names: list[str]) -> None:
        incoming = {name for name in display_names if name != "Controller"}
        for name in list(self.clients.keys()):
            client = self.clients[name]
            if name not in incoming and not client.simulated:
                self.remove_client(name)
        for name in incoming:
            if name not in self.clients:
                self.add_client(name)
