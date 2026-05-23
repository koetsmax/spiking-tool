"""Socket.IO event handlers for spiking-tool game clients."""

from __future__ import annotations

import traceback
from typing import Any, Awaitable, Callable, Optional

import socketio

import sot
from sot.AutomationManager import AutomationManager
from sot.ConnectionManager import ConnectionManager


class ClientState:
    def __init__(self) -> None:
        self.prev_port: Optional[int] = None


def _targets_this_client(client_names: list[str], local_name: str) -> bool:
    return local_name in client_names


def register_client_handlers(
    sio: socketio.AsyncClient,
    client_name: str,
    connection: ConnectionManager,
    automation: AutomationManager,
    state: Optional[ClientState] = None,
) -> ClientState:
    if state is None:
        state = ClientState()

    async def run_if_selected(
        data: list[str], action: Callable[[], Awaitable[Any]]
    ) -> None:
        if _targets_this_client(data, client_name):
            await action()

    @sio.event()
    async def region(data):
        connection.region = sot.region_from_name(data)
        print(f"Region set to {connection.region.city}")

    @sio.event()
    async def portspiking(data):
        connection.portspike = data
        print(f"Portspiking set to {connection.portspike}")

    @sio.event()
    async def client_ship(data):
        if data["client"] == client_name:
            await automation.set_ship(sio, data["ship_type"])

    @sio.event()
    async def launch_game(data):
        await run_if_selected(data, lambda: automation.launch_game(sio, leave=False))

    @sio.event()
    async def sail(data):
        await run_if_selected(data, lambda: automation.sail(sio, connection.portspike))

    @sio.event()
    async def rejoin_session(data):
        if _targets_this_client(data, client_name):
            await automation.rejoin_session(
                sio,
                connection.portspike,
                port=state.prev_port,
            )

    @sio.event()
    async def reset(data):
        if _targets_this_client(data, client_name):
            await automation.reset(sio, leave=True, portspiking=connection.portspike)

    @sio.event()
    async def kill_game(data):
        await run_if_selected(data, lambda: automation.kill_game(sio))

    @sio.event()
    async def stop_functions(data):
        await run_if_selected(data, lambda: automation.stop_functions(sio))

    @sio.event()
    async def auto_hold(data):
        await run_if_selected(data, lambda: automation.auto_hold(sio))

    @sio.event()
    async def hold_request(data):
        await run_if_selected(data, lambda: automation.hold_request(sio))

    @sio.event()
    async def invite_request(data):
        if data["clients"] == client_name:
            print("Inviting", data["person_to_invite"])
            await automation.invite_request(sio, data["person_to_invite"])

    @sio.event()
    async def forget_match(data):
        if _targets_this_client(data, client_name):
            state.prev_port = None
            connection.forget_last_match()
            print("Forgot last match — ready to detect management server again")

    async def on_join(ip, port):
        try:
            state.prev_port = int(port)
            await sio.emit("join", {"ip": ip, "port": port})
        except Exception:
            traceback.print_exc()

    connection.events.join += on_join  # pylint: disable=no-member

    return state
