from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import time

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel, QCheckBox, QComboBox, QPushButton, QWidget

    from controller_ui.client_columns import MetricState
    from spiking_tool.match import MatchDetails


_REJOIN_COPYABLE_STATUSES = frozenset({
    "Rejoining session",
    "Awaiting rejoin prompt",
    "Awaiting connection",
})


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
    return False


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
        self.last_match: Optional["MatchDetails"] = None
        self.holding = False
        self.afk_enabled = False
        self.afk_status = ""
        self.afk_toggle_button: Optional["QPushButton"] = None
        self.afk_status_label: Optional[QLabel] = None
        self.afk_countdown_deadline: Optional[float] = None
        self.afk_countdown_payload: Optional["AfkStatusPayload"] = None
        self.afk_show_status = False


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

        if match is not None:
            client.match = MatchDetails.from_payload(match)
            client.last_match = client.match
        elif _status_keeps_match_copyable(status, match):
            if client.match is None and client.last_match is not None:
                client.match = client.last_match
        else:
            client.match = None

        display_status, port = format_client_status(
            status, client.port, current_status=client.status
        )
        if port is not None:
            client.port = port

        match_for_region = client.match or client.last_match
        if (
            port is not None
            and selected_region
            and match_for_region is not None
            and not match_in_selected_region(match_for_region, selected_region)
        ):
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
        if client.afk_countdown_payload and client.afk_countdown_payload.type == "countdown":
            if remaining is None and client.afk_countdown_deadline is not None:
                remaining = int(client.afk_countdown_deadline - time.monotonic())
            text = client.afk_countdown_payload.display_text(remaining_seconds=remaining or 0)
        else:
            text = client.afk_status
        client.afk_status_label.setText(text)

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
            client.afk_status = ""
            client.afk_show_status = False
            self._render_client_afk_status(client)
            return

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
        if enabled:
            client.afk_show_status = False
            self._clear_client_afk_countdown(client)
            client.afk_status = ""
            if client.afk_status_label:
                client.afk_status_label.setText("")
                client.afk_status_label.setStyleSheet("")
        elif not preserve_status:
            client.afk_show_status = False
            self._clear_client_afk_countdown(client)
            client.afk_status = ""
            if client.afk_status_label:
                client.afk_status_label.setText("")
                client.afk_status_label.setStyleSheet("")
        if client.afk_toggle_button:
            style_afk_toggle_button(client.afk_toggle_button, enabled)

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
