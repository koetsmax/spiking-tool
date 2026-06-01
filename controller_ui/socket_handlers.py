"""Socket.IO event handlers for the controller window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controller_ui.main_window import ControllerWindow

logger = logging.getLogger(__name__)


def _log_roster_changes(controller: "ControllerWindow", roster: list[str]) -> None:
    current = {name for name in roster if name != "Controller"}
    previous = controller._connected_client_roster
    for name in sorted(current - previous):
        logger.info("Client connected: %s", name)
    for name in sorted(previous - current):
        logger.info("Client disconnected: %s", name)
    controller._connected_client_roster = current


def register_socket_handlers(controller: "ControllerWindow") -> None:
    @controller.sio.event()
    def connect():
        controller.request_client_roster()

    @controller.sio.event()
    def client_connect(data):
        _log_roster_changes(controller, data)
        controller.change_region()
        controller.set_port_spike()
        controller.set_desired_port_mode()
        controller.set_auto_spike_mode()
        controller.client_manager.sync_client_roster(data)
        controller.sort_client_list()
        controller.logging_tab.sync_client_list(controller._sorted_client_names())

    @controller.sio.event()
    def client_disconnect(data):
        _log_roster_changes(controller, data)
        controller.client_manager.sync_client_roster(data)
        controller.sort_client_list()
        controller.logging_tab.sync_client_list(controller._sorted_client_names())

    @controller.sio.event()
    def client_log(data):
        client_name = data["client"]
        message = data.get("message", "")
        if not message:
            return
        controller.log_store.append(client_name, message)
        controller.logging_tab.append_log(client_name, message)

    @controller.sio.event()
    def update_status(data):
        controller.client_manager.set_client_status(
            data["client"],
            data["status"],
            match=data.get("match"),
            selected_region=controller.region_combo.currentText(),
        )
        controller.client_manager.update_biggest_match(controller.biggest_match_label)
        controller.handle_automation_status(data)

    @controller.sio.event()
    def client_metric(data):
        controller.client_manager.set_client_metric(
            data["client"],
            data["metric"],
            data["state"],
        )

    @controller.sio.event()
    def afk_status(data):
        client_name = data.get("client")
        if not client_name:
            return
        payload = {key: value for key, value in data.items() if key != "client"}
        controller.client_manager.set_client_afk_status(client_name, payload)
        controller.refresh_afk_status_column_visibility()

    @controller.sio.event()
    def afk_state(data):
        controller.client_manager.set_client_afk_enabled(
            data["client"],
            bool(data.get("enabled")),
            preserve_status=bool(data.get("preserve_status")),
        )
        controller.refresh_afk_status_column_visibility()
