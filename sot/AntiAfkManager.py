"""In-client anti-AFK loop using ConnectionManager packet disconnect."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Awaitable, Callable, Literal, Optional

import keyboard

from spiking_tool.afk_status import (
    AFK_PHASE_ACTIVITY,
    AFK_PHASE_DISCONNECT,
    AFK_PHASE_ENABLED,
    AFK_PHASE_ERROR,
    AFK_PHASE_HAZELNUT_WAIT,
    AFK_PHASE_IDLE,
    AFK_PHASE_LOAD_IN,
    AFK_PHASE_LOADED,
    AFK_PHASE_POST_DISCONNECT_WAIT,
    AFK_PHASE_REJOIN_WAIT,
    AFK_PHASE_RESUME_LOADING,
    AfkStatusPayload,
    CountdownMode,
    format_elapsed,
)

from .ConnectionManager import ConnectionManager
from .SessionLoadTracker import SessionLoadTracker
from .ui_automation import GameScreenMatcher, SCREEN_POLL_SECONDS

logger = logging.getLogger(__name__)

StatusCallback = Callable[[dict], Awaitable[None]]
LogCallback = Callable[[str, str], None]
StateCallback = Callable[[bool, bool], Awaitable[None]]

DISCONNECT_SECONDS = 45
POST_DISCONNECT_WAIT_SECONDS = 8 * 60
AFK_STEP_PROGRESS_TIMEOUT_SECONDS = 11 * 60
HAZELNUT_IMAGE = "img/portspike_connected.png"
REJOIN_IMAGE = "img/rejoin_prompt.png"
KEY_PRESS_MULTIPLIER_RANGE = (0.25, 1.0)
KEY_HOLD_BASE_MS = 500
SLEEP_BASE_SECONDS = 120
WINDOW_FOCUS_DELAY_SECONDS = 0.2
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

AfkScreenState = Literal["rejoin", "hazelnut", "loading", "in_game"]


class AntiAfkManager:
    def __init__(
        self,
        connection: ConnectionManager,
        screen: Optional[GameScreenMatcher] = None,
    ) -> None:
        self._connection = connection
        self._screen = screen or GameScreenMatcher()
        self._session_load: Optional[SessionLoadTracker] = None
        self._enabled = False
        self._task: Optional[asyncio.Task] = None
        self._emit_status: Optional[StatusCallback] = None
        self._log: Optional[LogCallback] = None
        self._state_callback: Optional[StateCallback] = None
        self._cycle_count = 0
        self._started_at: Optional[datetime] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_status_callback(self, callback: StatusCallback) -> None:
        self._emit_status = callback

    def set_log_callback(self, callback: LogCallback) -> None:
        self._log = callback

    def set_state_callback(self, callback: StateCallback) -> None:
        self._state_callback = callback

    def set_session_load_tracker(self, tracker: SessionLoadTracker) -> None:
        self._session_load = tracker

    async def _notify_state(self, enabled: bool, *, preserve_status: bool = False) -> None:
        if self._state_callback:
            try:
                await self._state_callback(enabled, preserve_status)
            except Exception:
                pass

    def _write_log(self, message: str, level: str = "INFO") -> None:
        if self._log:
            self._log(message, level)
        else:
            logger.log(getattr(logging, level, logging.INFO), message)

    async def set_enabled(self, enabled: bool) -> None:
        if enabled:
            await self.start()
        else:
            await self.stop()

    async def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._cycle_count = 0
        self._started_at = datetime.now()
        self._write_log("Anti-AFK enabled")
        self._task = asyncio.create_task(self._run_loop())
        await self._notify_state(True)
        await self._emit(
            AfkStatusPayload(
                type="text",
                message="Running — starting cycle",
                phase=AFK_PHASE_ENABLED,
            ),
            log=False,
        )

    async def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        self._connection.force_disconnect = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._write_log("Anti-AFK disabled")
        self._log_runtime_summary(ended_label="Stopped at", level="INFO")
        await self._notify_state(False)
        await self._emit(AfkStatusPayload(type="clear"), log=False)

    def _log_runtime_summary(self, *, ended_label: str, level: str = "INFO") -> None:
        if self._started_at is None:
            return
        ended_at = datetime.now()
        elapsed_seconds = int((ended_at - self._started_at).total_seconds())
        self._write_log(f"Started at {self._started_at.strftime(DATETIME_FORMAT)}", level)
        self._write_log(
            f"{ended_label} {ended_at.strftime(DATETIME_FORMAT)} — ran for {format_elapsed(elapsed_seconds)}",
            level,
        )
        self._started_at = None

    async def _fatal_error(self, message: str) -> None:
        if not self._enabled:
            return
        self._enabled = False
        self._connection.force_disconnect = False
        await self._emit_error(message)
        self._write_log("Anti-AFK stopped due to error", "ERROR")
        self._log_runtime_summary(ended_label="Failed at", level="ERROR")
        await self._notify_state(False, preserve_status=True)

    def _with_cycle(self, payload: AfkStatusPayload) -> AfkStatusPayload:
        if payload.type == "clear":
            return payload
        return AfkStatusPayload(
            type=payload.type,
            message=payload.message,
            prefix=payload.prefix,
            seconds=payload.seconds,
            mode=payload.mode,
            cycle=self._cycle_count,
        )

    async def _emit(self, payload: AfkStatusPayload, *, log: bool = True) -> None:
        payload = self._with_cycle(payload)
        if log:
            text = payload.log_text()
            if payload.type == "error":
                self._write_log(text, "ERROR")
            elif text:
                self._write_log(text)
        if self._emit_status:
            try:
                await self._emit_status(payload.to_payload())
            except Exception:
                pass

    async def _emit_error(self, message: str) -> None:
        self._write_log(f"Error: {message}", "ERROR")
        await self._emit(
            AfkStatusPayload(type="error", message=message, phase=AFK_PHASE_ERROR),
            log=False,
        )

    async def _focus_game(self) -> bool:
        self._write_log("Focusing SoT window")
        self._screen.activate_window()
        await asyncio.sleep(WINDOW_FOCUS_DELAY_SECONDS)
        if self._screen.find_sot_hwnd() is None:
            return False
        return True

    def _step_deadline(self) -> float:
        return time.monotonic() + AFK_STEP_PROGRESS_TIMEOUT_SECONDS

    async def _fail_step_timeout(self, step_name: str) -> bool:
        await self._fatal_error(
            f"Timed out after {AFK_STEP_PROGRESS_TIMEOUT_SECONDS // 60} minutes during {step_name}"
        )
        return False

    async def _sleep_with_countdown(
        self,
        total_seconds: float,
        *,
        prefix: str,
        mode: CountdownMode = "seconds",
        log_message: str | None = None,
        phase: str | None = None,
        deadline: float | None = None,
    ) -> bool:
        """Sleep with countdown. Returns False if disabled or deadline expires first."""
        seconds = max(0, int(total_seconds))
        self._write_log(log_message or f"{prefix} {seconds}")
        await self._emit(
            AfkStatusPayload(
                type="countdown",
                prefix=prefix,
                seconds=seconds,
                mode=mode,
                phase=phase,
            ),
            log=False,
        )
        elapsed = 0.0
        while elapsed < total_seconds and self._enabled:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            sleep_for = min(1.0, total_seconds - elapsed)
            if deadline is not None:
                sleep_for = min(sleep_for, max(0.0, deadline - time.monotonic()))
                if sleep_for <= 0:
                    return False
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for
        return self._enabled

    async def _countdown_sleep(
        self,
        total_seconds: int,
        *,
        prefix: str,
        mode: CountdownMode = "seconds",
        log_message: str | None = None,
        phase: str | None = None,
        deadline: float | None = None,
    ) -> bool:
        return await self._sleep_with_countdown(
            total_seconds,
            prefix=prefix,
            mode=mode,
            log_message=log_message,
            phase=phase,
            deadline=deadline,
        )

    async def _press_key(self, key: str, *, base_ms: float = KEY_HOLD_BASE_MS) -> bool:
        if not await self._focus_game():
            await self._fatal_error("SoT window not found")
            return False
        multiplier = random.uniform(*KEY_PRESS_MULTIPLIER_RANGE)
        duration_ms = multiplier * base_ms
        self._write_log(f"Pressing {key} for {int(duration_ms)} ms")
        keyboard.press(key)
        await asyncio.sleep(duration_ms / 1000)
        keyboard.release(key)
        return True

    async def _sleep_between_actions(self) -> None:
        multiplier = random.uniform(*KEY_PRESS_MULTIPLIER_RANGE)
        duration = multiplier * SLEEP_BASE_SECONDS
        await self._sleep_with_countdown(
            duration,
            prefix="Idle before next cycle",
            mode="compact",
            log_message=f"Sleeping {int(duration)} seconds before next cycle",
            phase=AFK_PHASE_IDLE,
        )

    async def _wait_for_screen(
        self,
        image_path: str,
        message: str,
        *,
        phase: str | None = None,
        deadline: float | None = None,
    ) -> bool:
        self._write_log(f"Waiting for screen: {image_path}")
        await self._emit(
            AfkStatusPayload(type="text", message=message, phase=phase),
            log=False,
        )
        while self._enabled:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            if self._screen.screen_visible(image_path):
                self._write_log(f"Screen matched: {image_path}")
                return True
            sleep_for = SCREEN_POLL_SECONDS
            if deadline is not None:
                sleep_for = min(sleep_for, max(0.0, deadline - time.monotonic()))
                if sleep_for <= 0:
                    return False
            await asyncio.sleep(sleep_for)
        return False

    async def _disconnect_cycle(self) -> None:
        self._write_log("Starting packet disconnect")
        self._connection.force_disconnect = True
        try:
            await self._countdown_sleep(
                DISCONNECT_SECONDS,
                prefix="Dropping connection",
                mode="compact",
                log_message=f"Disconnect active for {DISCONNECT_SECONDS}s",
                phase=AFK_PHASE_DISCONNECT,
            )
        finally:
            self._connection.force_disconnect = False
            self._write_log("Stopping packet disconnect")

    async def _wait_after_disconnect(self, *, deadline: float) -> bool:
        if not await self._countdown_sleep(
            POST_DISCONNECT_WAIT_SECONDS,
            prefix="On connection error — waiting to accept",
            mode="compact",
            log_message=(
                f"Waiting {POST_DISCONNECT_WAIT_SECONDS // 60} minutes on connection error screen, "
                f"then accept and rejoin ({AFK_STEP_PROGRESS_TIMEOUT_SECONDS // 60} min step limit)"
            ),
            phase=AFK_PHASE_POST_DISCONNECT_WAIT,
            deadline=deadline,
        ):
            if not self._enabled:
                return False
            return await self._fail_step_timeout("connection error screen wait")
        return True

    def _detect_afk_screen_state(self) -> AfkScreenState:
        """Infer where we are in the AFK flow from the current game screen."""
        if self._screen.screen_visible(HAZELNUT_IMAGE):
            return "hazelnut"
        if self._screen.screen_visible(REJOIN_IMAGE):
            return "rejoin"
        loading_visible, _, _ = self._screen.loading_bar_visible()
        if loading_visible:
            return "loading"
        return "in_game"

    async def _accept_hazelnut(
        self,
        *,
        already_visible: bool = False,
        deadline: float | None = None,
    ) -> bool:
        if deadline is None:
            deadline = self._step_deadline()
        self._write_log(
            f"Accepting connection error ({AFK_STEP_PROGRESS_TIMEOUT_SECONDS // 60} minute step limit)"
        )
        if already_visible:
            await self._emit(
                AfkStatusPayload(
                    type="text",
                    message="Resuming — accepting connection error",
                    phase=AFK_PHASE_HAZELNUT_WAIT,
                ),
                log=False,
            )
        elif not await self._wait_for_screen(
            HAZELNUT_IMAGE,
            "Accepting connection error",
            phase=AFK_PHASE_HAZELNUT_WAIT,
            deadline=deadline,
        ):
            if not self._enabled:
                return False
            if time.monotonic() >= deadline:
                return await self._fail_step_timeout("accepting connection error")
            await self._fatal_error("Connection error screen not found")
            return False
        if not await self._press_key("enter", base_ms=1000):
            return False
        return True

    async def _accept_rejoin(
        self,
        *,
        already_visible: bool = False,
        deadline: float | None = None,
    ) -> bool:
        if deadline is None:
            deadline = self._step_deadline()
        if already_visible:
            self._write_log(
                f"Accepting rejoin prompt (already visible, "
                f"{AFK_STEP_PROGRESS_TIMEOUT_SECONDS // 60} minute step limit)"
            )
            await self._emit(
                AfkStatusPayload(
                    type="text",
                    message="Resuming at rejoin prompt",
                    phase=AFK_PHASE_REJOIN_WAIT,
                ),
                log=False,
            )
        else:
            self._write_log(
                f"Waiting for rejoin prompt after hazelnut "
                f"({AFK_STEP_PROGRESS_TIMEOUT_SECONDS // 60} minute step limit)"
            )
            if not await self._wait_for_screen(
                REJOIN_IMAGE,
                "Watching for rejoin prompt",
                phase=AFK_PHASE_REJOIN_WAIT,
                deadline=deadline,
            ):
                if not self._enabled:
                    return False
                if time.monotonic() >= deadline:
                    return await self._fail_step_timeout("rejoin prompt")
                await self._fatal_error("Rejoin prompt not found")
                return False
        if not await self._press_key("enter", base_ms=1000):
            return False
        return await self._wait_for_load_in()

    async def _resume_from_loading_bar(self) -> bool:
        """Loading bar visible — next screen may be in-world or connection error."""
        self._write_log("Loading bar visible while resuming AFK — polling for next screen")
        await self._emit(
            AfkStatusPayload(
                type="text",
                message="Resuming — loading bar visible",
                phase=AFK_PHASE_RESUME_LOADING,
            ),
            log=False,
        )
        while self._enabled:
            if self._screen.screen_visible(HAZELNUT_IMAGE):
                self._write_log("Connection error screen appeared during load")
                if not await self._accept_hazelnut(already_visible=True):
                    return False
                return await self._accept_rejoin()
            if self._screen.screen_visible(REJOIN_IMAGE):
                self._write_log("Rejoin prompt appeared during load")
                return await self._accept_rejoin(already_visible=True)
            loading_visible, dark_ratio, avg_lum = self._screen.loading_bar_visible()
            self._write_log(
                f"Loading bar poll — {'visible' if loading_visible else 'not visible'} "
                f"(dark {dark_ratio * 100:.0f}%, avg lum {avg_lum:.0f})"
            )
            if not loading_visible:
                if await self._screen.confirm_loading_bar_gone(
                    log=self._write_log,
                    should_continue=lambda: self._enabled,
                ):
                    self._write_log("Loading bar cleared — confirmed back in world")
                    await self._emit(
                        AfkStatusPayload(
                            type="text",
                            message="Back in world",
                            phase=AFK_PHASE_LOADED,
                        ),
                        log=False,
                    )
                    await self._sleep_between_actions()
                    return True
                self._write_log("Loading bar still visible after confirm wait — continuing poll")
            await asyncio.sleep(SCREEN_POLL_SECONDS)
        return False

    async def _resume_from_detected_screen(self) -> bool:
        """Continue the AFK cycle from the current game screen instead of restarting."""
        if not await self._focus_game():
            await self._fatal_error("SoT window not found")
            return False

        screen_state = self._detect_afk_screen_state()
        self._write_log(f"Resuming AFK from detected screen: {screen_state}")

        if screen_state == "hazelnut":
            if not await self._accept_hazelnut(already_visible=True):
                return False
            if not await self._accept_rejoin():
                return False
            await self._sleep_between_actions()
            return True

        if screen_state == "rejoin":
            if not await self._accept_rejoin(already_visible=True):
                return False
            await self._sleep_between_actions()
            return True

        if screen_state == "loading":
            return await self._resume_from_loading_bar()

        await self._emit(
            AfkStatusPayload(
                type="text",
                message="Resuming in world",
                phase=AFK_PHASE_LOADED,
            ),
            log=False,
        )
        await self._sleep_between_actions()
        return True

    async def _wait_for_load_in(self) -> bool:
        self._write_log("Waiting for load-in (bottom loading bar)")
        await self._emit(
            AfkStatusPayload(
                type="text",
                message="Loading into world",
                phase=AFK_PHASE_LOAD_IN,
            ),
            log=False,
        )
        if self._session_load is None:
            await self._fatal_error("Load tracker not configured")
            return False
        self._session_load.begin_load_wait()
        if not await self._session_load.wait_until_loaded(
            should_continue=lambda: self._enabled,
        ):
            if self._enabled:
                await self._fatal_error("Timed out waiting to load in")
            return False
        await self._emit(
            AfkStatusPayload(
                type="text",
                message="Back in world",
                phase=AFK_PHASE_LOADED,
            ),
            log=False,
        )
        self._write_log("Load-in complete (loading bar gone)")
        return True

    async def _run_full_cycle(self) -> bool:
        await self._disconnect_cycle()
        hazelnut_deadline = self._step_deadline()
        if not await self._wait_after_disconnect(deadline=hazelnut_deadline):
            return False
        if not await self._accept_hazelnut(deadline=hazelnut_deadline):
            return False
        rejoin_deadline = self._step_deadline()
        if not await self._accept_rejoin(deadline=rejoin_deadline):
            return False
        await self._sleep_between_actions()
        return True

    async def _run_loop(self) -> None:
        try:
            if not await self._resume_from_detected_screen():
                return
            while self._enabled:
                await self._emit(
                    AfkStatusPayload(
                        type="text",
                        message="Pressing Space",
                        phase=AFK_PHASE_ACTIVITY,
                    ),
                    log=False,
                )
                if not await self._press_key("space"):
                    break
                if not await self._run_full_cycle():
                    break
                self._cycle_count += 1
        except asyncio.CancelledError:
            self._connection.force_disconnect = False
            self._write_log("Anti-AFK loop cancelled")
            raise
        except Exception:
            self._write_log("Anti-AFK loop failed", "ERROR")
            if not self._log:
                logger.exception("Anti-AFK loop failed")
            self._enabled = False
            self._connection.force_disconnect = False
            await self._emit(
                AfkStatusPayload(
                    type="error",
                    message="Anti-AFK loop failed",
                    phase=AFK_PHASE_ERROR,
                ),
                log=False,
            )
            self._log_runtime_summary(ended_label="Failed at", level="ERROR")
            await self._notify_state(False, preserve_status=True)
