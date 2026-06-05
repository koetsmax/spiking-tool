"""Socket.IO event handlers for spiking-tool game clients."""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from typing import Any, Awaitable, Callable, Optional

import socketio

import sot
from sot.AntiAfkManager import AntiAfkManager
from sot.AutomationManager import AutomationManager
from sot.ConnectionManager import ConnectionManager
from sot.SessionLoadTracker import SessionLoadTracker
from spiking_tool.client_session import ClientSessionState
from spiking_tool.client_socket import safe_emit
from spiking_tool.client_logging import (
    attach_client_log_transport,
    client_log,
    start_client_log_pump,
)
from spiking_tool.periodic_checks import (
    PeriodicCheckContext,
    PeriodicCheckResult,
    PeriodicCheckRunner,
    default_periodic_checks,
)
logger = logging.getLogger(__name__)

# Backward-compatible alias
ClientState = ClientSessionState


def register_client_handlers(
    sio: socketio.AsyncClient,
    client_name: str,
    connection: ConnectionManager,
    automation: AutomationManager,
    anti_afk_manager: AntiAfkManager,
    state: Optional[ClientSessionState] = None,
) -> tuple[ClientSessionState, PeriodicCheckRunner]:
    if state is None:
        state = ClientSessionState()

    identity = {"display_name": client_name}

    def selected_client_names(data) -> list[str]:
        if isinstance(data, dict):
            return data.get("clients", [])
        return data

    def is_selected(data) -> bool:
        return identity["display_name"] in selected_client_names(data)

    async def emit_client_status(status, *, match: Optional[dict[str, Any]] = None) -> None:
        state.record_status(status, match=match)
        if match is not None:
            await safe_emit(sio, "update_status", {"status": status, "match": match})
        else:
            await safe_emit(sio, "update_status", status)

    async def emit_afk_status(payload: dict) -> None:
        state.record_afk_status(payload)
        await safe_emit(sio, "afk_status", payload)

    async def emit_afk_state(enabled: bool, preserve_status: bool = False) -> None:
        await safe_emit(
            sio,
            "afk_state",
            {"enabled": enabled, "preserve_status": preserve_status},
        )

    async def on_afk_state_changed(enabled: bool, preserve_status: bool = False) -> None:
        await emit_afk_state(enabled, preserve_status)

    async def sync_session_to_server() -> None:
        """Push remembered state after reconnecting to the server/controller."""
        connection.region = sot.region_from_name(state.region_name)
        connection.portspike = state.portspike
        automation.ship = state.ship_type
        await safe_emit(sio, "region", state.region_name)
        await safe_emit(sio, "portspiking", state.portspike)
        await emit_client_status(
            state.last_status,
            match=state.last_match,
        )
        await safe_emit(sio, "ship_state", {"ship_type": state.ship_type})
        await emit_afk_state(anti_afk_manager.enabled, preserve_status=True)
        if state.last_afk_status is not None:
            await emit_afk_status(state.last_afk_status)
        await safe_emit(sio, "client_metric", _pending_resolution_metric(automation))
        client_log("Reconnected — restored session state to controller", "INFO")

    automation.set_status_emitter(emit_client_status)
    anti_afk_manager.set_status_callback(emit_afk_status)
    anti_afk_manager.set_log_callback(
        lambda message, level="INFO": client_log(f"[AFK] {message}", level)
    )

    session_load = SessionLoadTracker(
        automation.screen,
        should_stop=lambda: automation.stop,
        log=lambda message, level="INFO": client_log(f"[Load] {message}", level),
    )
    automation.set_session_load_tracker(session_load)
    anti_afk_manager.set_session_load_tracker(session_load)

    async def on_periodic_check_failure(result: PeriodicCheckResult) -> None:
        client_log(
            f"[Health] {result.check_id}: {result.message}",
            result.level,
        )
        await emit_client_status(result.message)
        if anti_afk_manager.enabled:
            await anti_afk_manager.stop()

    periodic_checks = PeriodicCheckRunner(
        default_periodic_checks(automation.screen),
        context=PeriodicCheckContext(
            screen=automation.screen,
            on_failure=on_periodic_check_failure,
            should_run=lambda: anti_afk_manager.enabled,
            log=lambda message, level="INFO": client_log(f"[Health] {message}", level),
        ),
    )

    async def on_afk_state_changed(enabled: bool, preserve_status: bool = False) -> None:
        await emit_afk_state(enabled, preserve_status)
        if enabled:
            client_log("[Health] Anti-AFK enabled — periodic checks will run now", "INFO")

    anti_afk_manager.set_state_callback(on_afk_state_changed)
    periodic_checks.start()
    logger.info(
        "Periodic health checks registered (%s) — active while anti-AFK is enabled",
        ", ".join(periodic_checks.check_ids),
    )

    async def shutdown(_data=None) -> None:
        client_log("Shutdown requested from controller", "INFO")
        automation.stop = True
        await periodic_checks.stop()
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
        attach_client_log_transport(sio, identity["display_name"])
        start_client_log_pump()
        logger.info("Connected to server; restoring session state")
        await sync_session_to_server()
        asyncio.create_task(automation.emit_resolution_metric(sio, force=True))

    @sio.event()
    async def disconnect():
        client_log(
            "Disconnected from server — local automation continues; will retry connection",
            "WARNING",
        )
        logger.warning("Disconnected from server; will retry connection")

    @sio.event()
    async def request_session_sync(data=None):
        del data
        logger.info("Controller online — re-syncing session state to server")
        await sync_session_to_server()

    @sio.event()
    async def anti_afk(data):
        if not isinstance(data, dict):
            return
        enabled = bool(data.get("enabled"))
        client_log(f"[AFK] Controller set anti-AFK to {enabled}", "INFO")
        await anti_afk_manager.set_enabled(enabled)

    @sio.event()
    async def client_identity(data):
        identity["display_name"] = data["display_name"]
        attach_client_log_transport(sio, identity["display_name"])
        client_log(f"Assigned controller name: {identity['display_name']}", "INFO")

    async def run_if_selected(data, action: Callable[[], Awaitable[Any]]) -> None:
        if is_selected(data):
            await action()

    @sio.event()
    async def region(data):
        connection.region = sot.region_from_name(data)
        state.record_region(data)
        print(f"Region set to {connection.region.city}")

    @sio.event()
    async def portspiking(data):
        connection.portspike = data
        state.record_portspike(bool(data))
        if not data:
            connection.clear_disconnect()
        print(f"Portspiking set to {connection.portspike}")

    @sio.event()
    async def client_ship(data):
        if data["client"] != identity["display_name"]:
            return
        ship_type = data["ship_type"]
        state.record_ship(ship_type)
        if automation.ship == ship_type:
            return
        await automation.set_ship(sio, ship_type)

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
            session_load.cancel()
            session_load.forget_match()
            if connection.portspike:
                connection.begin_portspike_cycle()
            else:
                connection.forget_last_match()
            await automation.reset(sio, leave=True, portspiking=connection.portspike)

    @sio.event()
    async def kill_game(data):
        await run_if_selected(data, lambda: automation.kill_game(sio))

    @sio.event()
    async def stop_functions(data):
        await run_if_selected(data, lambda: automation.stop_functions(sio))

    @sio.event()
    async def invite_request(data):
        if data["clients"] == identity["display_name"]:
            print("Inviting", data["person_to_invite"])
            await automation.invite_request(sio, data["person_to_invite"])

    @sio.event()
    async def forget_match(data):
        if is_selected(data):
            state.prev_port = None
            state.last_match = None
            session_load.cancel()
            session_load.forget_match()
            connection.forget_last_match()
            await emit_client_status("Pending...")
            client_log("Forgot last match", "INFO")

    @sio.event()
    async def fix_resolution(data):
        await run_if_selected(data, lambda: automation.report_game_resolution(sio))

    async def on_join(match_data):
        try:
            game = f"{match_data['game_ip']}:{match_data['game_port']}"
            management = f"{match_data['management_ip']}:{match_data['management_port']}"
            client_log(f"Join match game={game} management={management}", "INFO")
            state.prev_port = int(match_data["management_port"])
            session_load.record_match(state.prev_port)
            state.record_status(match_data["management_port"], match=match_data)
            await safe_emit(sio, "join", match_data)
            if session_load.reset_waiting:
                await emit_client_status(session_load.waiting_to_load_status())
            elif session_load.monitoring and not session_load.loaded:
                await emit_client_status(session_load.loading_status())
        except Exception:
            traceback.print_exc()

    connection.events.join += on_join  # pylint: disable=no-member

    return state, periodic_checks


def _pending_resolution_metric(automation: AutomationManager) -> dict[str, str]:
    result = automation.screen.check_target_resolution()
    return {
        "metric": "resolution",
        "state": automation.resolution_metric_state(result),
    }
