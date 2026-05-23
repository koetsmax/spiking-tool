from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QCheckBox, QComboBox


class Client:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ship_type = "Brigantine"
        self.status = "Pending..."
        self.active_checkbox: Optional[QCheckBox] = None
        self.name_label: Optional[QLabel] = None
        self.ship_combo: Optional[QComboBox] = None
        self.status_label: Optional[QLabel] = None
        self.port: Optional[str] = None
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

    def set_client_status(self, name: str, status) -> None:
        from spiking_tool.ports import format_client_status

        client = self.get_client(name)
        if not client:
            return

        display_status, port = format_client_status(status, client.port)
        if port is not None:
            client.port = port
        client.status = display_status
        if client.status_label:
            client.status_label.setText(str(client.status))

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

    def get_biggest_match(self) -> Optional[int]:
        return self.biggest_match

    def sort_clients_by_name(self) -> None:
        def get_numeric_part(key: str) -> int:
            return int(key[3:])

        self.clients = dict(sorted(self.clients.items(), key=lambda x: get_numeric_part(x[0])))
