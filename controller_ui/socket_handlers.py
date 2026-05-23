"""Socket.IO event handlers for the controller window."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controller_ui.main_window import ControllerWindow


def register_socket_handlers(controller: "ControllerWindow") -> None:
    @controller.sio.event()
    def client_connect(data):
        controller.change_region()
        controller.set_port_spike()
        controller.set_desired_port_mode()
        controller.set_auto_spike_mode()
        for client in data:
            if client != "Controller" and client not in controller.client_manager.clients:
                controller.client_manager.add_client(client)
        controller.sort_client_list()

    @controller.sio.event()
    def client_disconnect(data):
        for client_name, client in controller.client_manager.clients.copy().items():
            if client_name not in data:
                if client.holding:
                    print(f"{client_name} DISCONNECTED WHILE HOLDING A SHIP!!!!")
                controller.client_manager.remove_client(client_name)
        controller.sort_client_list()

    @controller.sio.event()
    def update_status(data):
        controller.client_manager.set_client_status(
            data["client"],
            data["status"],
            match=data.get("match"),
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
