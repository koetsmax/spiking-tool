"""Socket.IO event handlers for spiking-tool game clients."""

from __future__ import annotations

import asyncio
import os
import traceback
from typing import Any, Awaitable, Callable, Optional

import socketio

import sot
from sot.AutomationManager import AutomationManager
from sot.ConnectionManager import ConnectionManager
from spiking_tool.remote_log import remote_log_bridge


class ClientState:
    def __init__(self) -> None:
        self.prev_port: Optional[int] = None


def register_client_handlers(
    sio: socketio.AsyncClient,
    client_name: str,
    connection: ConnectionManager,
    automation: AutomationManager,
    state: Optional[ClientState] = None,
) -> ClientState:
    if state is None:
        state = ClientState()

    identity = {"display_name": client_name}

    def is_selected(client_names: list[str]) -> bool:
        return identity["display_name"] in client_names

    async def shutdown(_data=None) -> None:
        remote_log_bridge.enqueue("Shutdown requested from controller", "INFO")
        automation.stop = True
        connection.stop()
        os._exit(0)

    @sio.event()
    async def shutdown_client(data=None):
        del data
        await shutdown()

    @sio.event()
    async def connect():
        remote_log_bridge.attach(sio, identity["display_name"])
        remote_log_bridge.start_pump_task()
        asyncio.create_task(automation.emit_resolution_metric(sio, force=True))

    @sio.event()
    async def client_identity(data):
        identity["display_name"] = data["display_name"]
        remote_log_bridge.attach(sio, identity["display_name"])
        remote_log_bridge.enqueue(f"Assigned controller name: {identity['display_name']}", "INFO")

    async def run_if_selected(data: list[str], action: Callable[[], Awaitable[Any]]) -> None:
        if is_selected(data):
            await action()

    @sio.event()
    async def region(data):
        connection.region = sot.region_from_name(data)
        print(f"Region set to {connection.region.city}")

    @sio.event()
    async def portspiking(data):
        connection.portspike = data
        if not data:
            connection.clear_disconnect()
        print(f"Portspiking set to {connection.portspike}")

    @sio.event()
    async def client_ship(data):
        if data["client"] == identity["display_name"]:
            await automation.set_ship(sio, data["ship_type"])

    @sio.event()
    async def launch_game(data):
        await run_if_selected(data, lambda: automation.launch_game(sio, leave=False))

    @sio.event()
    async def sail(data):
        async def action() -> None:
            connection.clear_disconnect()
            await automation.sail(sio, connection.portspike)

        await run_if_selected(data, action)

    @sio.event()
    async def rejoin_session(data):
        if is_selected(data):
            connection.clear_disconnect()
            await automation.rejoin_session(
                sio,
                connection.portspike,
                port=state.prev_port,
            )

    @sio.event()
    async def reset(data):
        if is_selected(data):
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
        if data["clients"] == identity["display_name"]:
            print("Inviting", data["person_to_invite"])
            await automation.invite_request(sio, data["person_to_invite"])

    @sio.event()
    async def forget_match(data):
        if is_selected(data):
            state.prev_port = None
            connection.forget_last_match()
            print("Forgot last match — ready to detect management server again")

    @sio.event()
    async def fix_resolution(data):
        await run_if_selected(data, lambda: automation.report_game_resolution(sio))

    async def on_join(match_data):
        try:
            state.prev_port = int(match_data["management_port"])
            await sio.emit("join", match_data)
        except Exception:
            traceback.print_exc()

    connection.events.join += on_join  # pylint: disable=no-member

    return state
