"""In-client anti-AFK loop using ConnectionManager packet disconnect."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Awaitable, Callable, Optional

import keyboard

from spiking_tool.afk_status import AfkStatusPayload, CountdownMode, format_elapsed

from .ConnectionManager import ConnectionManager
from .ui_automation import GameScreenMatcher, SCREEN_POLL_SECONDS

logger = logging.getLogger(__name__)

StatusCallback = Callable[[dict], Awaitable[None]]
LogCallback = Callable[[str, str], None]
StateCallback = Callable[[bool, bool], Awaitable[None]]

DISCONNECT_SECONDS = 45
POST_DISCONNECT_WAIT_SECONDS = 8 * 60
HAZELNUT_WAIT_SECONDS = 20
REJOIN_WAIT_SECONDS = 45
HAZELNUT_IMAGE = "img/portspike_connected_old.png"
REJOIN_IMAGE = "img/rejoin_prompt.png"
KEY_PRESS_MULTIPLIER_RANGE = (0.25, 1.0)
KEY_HOLD_BASE_MS = 500
SLEEP_BASE_SECONDS = 120
WINDOW_FOCUS_DELAY_SECONDS = 0.2
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class AntiAfkManager:
    def __init__(
        self,
        connection: ConnectionManager,
        screen: Optional[GameScreenMatcher] = None,
    ) -> None:
        self._connection = connection
        self._screen = screen or GameScreenMatcher()
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

    async def _notify_state(self, enabled: bool, *, preserve_status: bool = False) -> None:
        if self._state_callback:
            await self._state_callback(enabled, preserve_status)

    def _write_log(self, message: str, level: str = "INFO") -> None:
        if self._log:
            self._log(message, level)
            return
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
        await self._emit(AfkStatusPayload(type="text", message="Enabled"), log=False)

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
            await self._emit_status(payload.to_payload())

    async def _emit_error(self, message: str) -> None:
        self._write_log(f"Error: {message}", "ERROR")
        await self._emit(AfkStatusPayload(type="error", message=message), log=False)

    async def _focus_game(self) -> bool:
        self._write_log("Focusing SoT window")
        self._screen.activate_window()
        await asyncio.sleep(WINDOW_FOCUS_DELAY_SECONDS)
        if self._screen.find_sot_hwnd() is None:
            return False
        return True

    async def _sleep_with_countdown(
        self,
        total_seconds: float,
        *,
        prefix: str,
        mode: CountdownMode = "seconds",
        log_message: str | None = None,
    ) -> None:
        seconds = max(0, int(total_seconds))
        self._write_log(log_message or f"{prefix} {seconds}")
        await self._emit(
            AfkStatusPayload(
                type="countdown",
                prefix=prefix,
                seconds=seconds,
                mode=mode,
            ),
            log=False,
        )
        elapsed = 0.0
        while elapsed < total_seconds and self._enabled:
            sleep_for = min(1.0, total_seconds - elapsed)
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for

    async def _countdown_sleep(
        self,
        total_seconds: int,
        *,
        prefix: str,
        mode: CountdownMode = "seconds",
        log_message: str | None = None,
    ) -> None:
        await self._sleep_with_countdown(
            total_seconds,
            prefix=prefix,
            mode=mode,
            log_message=log_message,
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
            prefix="Sleep",
            mode="compact",
            log_message=f"Sleeping {int(duration)} seconds before next cycle",
        )

    async def _wait_for_screen(self, image_path: str, message: str) -> bool:
        self._write_log(f"Waiting for screen: {image_path}")
        await self._emit(AfkStatusPayload(type="text", message=message), log=False)
        while self._enabled:
            if self._screen.screen_visible(image_path):
                self._write_log(f"Screen matched: {image_path}")
                return True
            await asyncio.sleep(SCREEN_POLL_SECONDS)
        return False

    async def _disconnect_cycle(self) -> None:
        self._write_log("Starting packet disconnect")
        self._connection.force_disconnect = True
        try:
            await self._countdown_sleep(
                DISCONNECT_SECONDS,
                prefix="Disconnect",
                mode="compact",
                log_message=f"Disconnect active for {DISCONNECT_SECONDS}s",
            )
        finally:
            self._connection.force_disconnect = False
            self._write_log("Stopping packet disconnect")

    async def _wait_after_disconnect(self) -> None:
        await self._countdown_sleep(
            POST_DISCONNECT_WAIT_SECONDS,
            prefix="Wait",
            mode="compact",
            log_message=f"Sleeping {POST_DISCONNECT_WAIT_SECONDS // 60} minutes before hazelnut prompt",
        )

    async def _accept_hazelnut(self) -> bool:
        self._write_log("Accepting hazelnut error")
        if not await self._wait_for_screen(HAZELNUT_IMAGE, "Hazelnut"):
            await self._fatal_error("Hazelnut screen not found")
            return False
        if not await self._press_key("enter", base_ms=1000):
            return False
        await self._sleep_with_countdown(
            HAZELNUT_WAIT_SECONDS,
            prefix="Wait",
            mode="compact",
            log_message=f"Sleeping {HAZELNUT_WAIT_SECONDS}s after hazelnut prompt",
        )
        return True

    async def _accept_rejoin(self) -> bool:
        self._write_log("Accepting rejoin prompt")
        if not await self._wait_for_screen(REJOIN_IMAGE, "Rejoin"):
            await self._fatal_error("Rejoin prompt not found")
            return False
        if not await self._press_key("enter", base_ms=1000):
            return False
        await self._sleep_with_countdown(
            REJOIN_WAIT_SECONDS,
            prefix="Wait",
            mode="compact",
            log_message=f"Sleeping {REJOIN_WAIT_SECONDS}s after rejoin prompt",
        )
        return True

    async def _run_full_cycle(self) -> bool:
        await self._disconnect_cycle()
        await self._wait_after_disconnect()
        if not await self._accept_hazelnut():
            return False
        if not await self._accept_rejoin():
            return False
        await self._sleep_between_actions()
        return True

    async def _run_loop(self) -> None:
        try:
            while self._enabled:
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
                AfkStatusPayload(type="error", message="Anti-AFK loop failed"),
                log=False,
            )
            self._log_runtime_summary(ended_label="Failed at", level="ERROR")
            await self._notify_state(False, preserve_status=True)
