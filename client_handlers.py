"""Socket.IO event handlers for spiking-tool game clients."""

from __future__ import annotations

import asyncio
import os
import traceback
from typing import Any, Awaitable, Callable, Optional

import socketio

import sot
from sot.AntiAfkManager import AntiAfkManager
from sot.AutomationManager import AutomationManager
from sot.ConnectionManager import ConnectionManager
from sot.SessionLoadTracker import SessionLoadTracker
from spiking_tool.remote_log import remote_log_bridge


class ClientState:
    def __init__(self) -> None:
        self.prev_port: Optional[int] = None
        self.connected_once = False


def register_client_handlers(
    sio: socketio.AsyncClient,
    client_name: str,
    connection: ConnectionManager,
    automation: AutomationManager,
    anti_afk_manager: AntiAfkManager,
    state: Optional[ClientState] = None,
) -> ClientState:
    if state is None:
        state = ClientState()

    identity = {"display_name": client_name}

    def selected_client_names(data) -> list[str]:
        if isinstance(data, dict):
            return data.get("clients", [])
        return data

    def is_selected(data) -> bool:
        return identity["display_name"] in selected_client_names(data)

    async def shutdown(_data=None) -> None:
        remote_log_bridge.enqueue("Shutdown requested from controller", "INFO")
        automation.stop = True
        await anti_afk_manager.stop()
        connection.stop()
        os._exit(0)

    @sio.event()
    async def shutdown_client(data=None):
        del data
        await shutdown()

    @sio.event()
    async def connect():
        state.connected_once = True
        remote_log_bridge.attach(sio, identity["display_name"])
        remote_log_bridge.start_pump_task()
        asyncio.create_task(automation.emit_resolution_metric(sio, force=True))
        await sio.emit("afk_state", {"enabled": anti_afk_manager.enabled})

    async def emit_afk_status(payload: dict) -> None:
        await sio.emit("afk_status", payload)

    async def emit_afk_state(enabled: bool, preserve_status: bool = False) -> None:
        await sio.emit(
            "afk_state",
            {"enabled": enabled, "preserve_status": preserve_status},
        )

    anti_afk_manager.set_status_callback(emit_afk_status)
    anti_afk_manager.set_state_callback(emit_afk_state)
    anti_afk_manager.set_log_callback(
        lambda message, level="INFO": remote_log_bridge.enqueue(f"[AFK] {message}", level)
    )

    session_load = SessionLoadTracker(
        automation.screen,
        should_stop=lambda: automation.stop,
        log=lambda message, level="INFO": remote_log_bridge.enqueue(f"[Load] {message}", level),
    )
    automation.set_session_load_tracker(session_load)

    async def emit_client_status(status) -> None:
        await sio.emit("update_status", data=status)

    @sio.event()
    async def anti_afk(data):
        if not isinstance(data, dict):
            return
        enabled = bool(data.get("enabled"))
        remote_log_bridge.enqueue(f"[AFK] Controller set anti-AFK to {enabled}", "INFO")
        await anti_afk_manager.set_enabled(enabled)

    @sio.event()
    async def client_identity(data):
        identity["display_name"] = data["display_name"]
        remote_log_bridge.attach(sio, identity["display_name"])
        remote_log_bridge.enqueue(f"Assigned controller name: {identity['display_name']}", "INFO")

    async def run_if_selected(data, action: Callable[[], Awaitable[Any]]) -> None:
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
        sail_delay = data.get("sail_delay_seconds", 0) if isinstance(data, dict) else 0

        async def action() -> None:
            if sail_delay > 0:
                await asyncio.sleep(sail_delay)
            connection.clear_disconnect()
            await automation.sail(sio, connection.portspike)
            if not connection.portspike:
                await session_load.start(emit_client_status)

        await run_if_selected(data, action)

    @sio.event()
    async def rejoin_session(data):
        if is_selected(data):
            if connection.portspike:
                connection.begin_portspike_cycle()
            else:
                connection.clear_disconnect()
            await automation.rejoin_session(
                sio,
                connection.portspike,
                port=state.prev_port,
            )

    @sio.event()
    async def reset(data):
        if is_selected(data):
            if connection.portspike:
                connection.begin_portspike_cycle()
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
            session_load.cancel()
            session_load.forget_match()
            connection.forget_last_match()
            await emit_client_status("Pending...")
            remote_log_bridge.enqueue("Forgot last match", "INFO")

    @sio.event()
    async def fix_resolution(data):
        await run_if_selected(data, lambda: automation.report_game_resolution(sio))

    async def on_join(match_data):
        try:
            state.prev_port = int(match_data["management_port"])
            session_load.record_match(state.prev_port)
            await sio.emit("join", match_data)
            if session_load.reset_waiting:
                await emit_client_status(session_load.waiting_to_load_status())
            elif session_load.monitoring and not session_load.loaded:
                await emit_client_status(session_load.loading_status())
        except Exception:
            traceback.print_exc()

    connection.events.join += on_join  # pylint: disable=no-member

    return state
