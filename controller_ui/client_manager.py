from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QCheckBox, QComboBox, QWidget

    from controller_ui.client_columns import MetricState
    from spiking_tool.match import MatchDetails


class Client:
    def __init__(self, name: str) -> None:
        self.name = name
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
        self.holding = False


class ClientManager:
    def __init__(self) -> None:
        self.clients: dict[str, Client] = {}
        self.biggest_match: Optional[int] = None

    def add_client(self, name: str) -> None:
        self.clients[name] = Client(name)

    def get_active_clients(self) -> list[str]:
        return [
            name
            for name, client in self.clients.items()
            if client.active_checkbox and client.active_checkbox.isChecked()
        ]

    def get_client(self, name: str) -> Optional[Client]:
        return self.clients.get(name)

    def set_client_status(self, name: str, status, match=None) -> None:
        from controller_ui.client_columns import ClickableStatusLabel
        from spiking_tool.match import MatchDetails
        from spiking_tool.ports import format_client_status

        client = self.get_client(name)
        if not client:
            return

        if match is not None:
            client.match = MatchDetails.from_payload(match)

        display_status, port = format_client_status(status, client.port)
        if port is not None:
            client.port = port
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

    def remove_client(self, name: str) -> None:
        if name in self.clients:
            del self.clients[name]

    def update_biggest_match(self, label: QLabel) -> None:
        port_counts: dict[str, list[str]] = {}
        for client_name, client in self.clients.items():
            if client.port is not None:
                port_counts.setdefault(client.port, []).append(client_name)

        biggest_match = None
        for port, clients in port_counts.items():
            if biggest_match is None or len(clients) > len(port_counts[biggest_match]):
                biggest_match = port

        if biggest_match:
            matching_clients = ", ".join(port_counts[biggest_match])
            num_matching_clients = len(port_counts[biggest_match])
            label.setText(
                f"Biggest match: {num_matching_clients} on port {biggest_match} "
                f"({matching_clients})"
            )
            self.biggest_match = num_matching_clients
        else:
            label.setText("No matches found")
            self.biggest_match = None

    def reset_clients(self) -> None:
        for client in self.clients.values():
            client.port = None
            client.match = None

    def get_biggest_match(self) -> Optional[int]:
        return self.biggest_match

    def sort_clients_by_name(self) -> None:
        from spiking_tool.client_identity import sort_display_name_key

        self.clients = dict(
            sorted(self.clients.items(), key=lambda item: sort_display_name_key(item[0]))
        )

    def sync_client_roster(self, display_names: list[str]) -> None:
        incoming = {name for name in display_names if name != "Controller"}
        for name in list(self.clients.keys()):
            if name not in incoming:
                self.remove_client(name)
        for name in incoming:
            if name not in self.clients:
                self.add_client(name)
