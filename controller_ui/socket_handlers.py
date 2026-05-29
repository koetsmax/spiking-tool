"""Socket.IO event handlers for the controller window."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controller_ui.main_window import ControllerWindow


def register_socket_handlers(controller: "ControllerWindow") -> None:
    @controller.sio.event()
    def connect():
        controller.request_client_roster()

    @controller.sio.event()
    def client_connect(data):
        controller.change_region()
        controller.set_port_spike()
        controller.set_desired_port_mode()
        controller.set_auto_spike_mode()
        controller.client_manager.sync_client_roster(data)
        controller.sort_client_list()
        controller.logging_tab.sync_client_list(controller._sorted_client_names())

    @controller.sio.event()
    def client_disconnect(data):
        for client_name, client in controller.client_manager.clients.copy().items():
            if client_name not in data and client.holding:
                print(f"{client_name} DISCONNECTED WHILE HOLDING A SHIP!!!!")
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
    def hold_request_ack(data):
        client = controller.client_manager.get_client(data["client"])
        if client:
            client.holding = True
            print(f"{client.name} is now holding")
