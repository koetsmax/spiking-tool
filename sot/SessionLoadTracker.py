"""Track world load-in after set sail and expose loading status for the controller."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from spiking_tool.ports import normalize_port_digits

from .ui_automation import SCREEN_POLL_SECONDS, GameScreenMatcher

logger = logging.getLogger(__name__)

NO_LOADING_SEEN_TIMEOUT_SECONDS = 15.0
LOAD_WAIT_TIMEOUT_SECONDS = 600.0

LogCallback = Callable[[str, str], None]


class SessionLoadTracker:
    def __init__(
        self,
        screen: GameScreenMatcher,
        *,
        should_stop: Callable[[], bool] | None = None,
        log: LogCallback | None = None,
    ) -> None:
        self._screen = screen
        self._should_stop = should_stop or (lambda: False)
        self._log = log
        self._task: Optional[asyncio.Task] = None
        self._matched_port: Optional[str] = None
        self._loaded = False
        self._monitoring = False
        self._reset_waiting = False

    def waiting_to_load_status(self) -> str:
        if self._matched_port:
            return f"{self._matched_port} - Waiting to load"
        return "Waiting to load"

    @property
    def reset_waiting(self) -> bool:
        return self._reset_waiting

    def begin_reset_wait(self) -> None:
        """Stop sail-load status updates while reset waits for load-in."""
        self.cancel()
        self._reset_waiting = True

    def end_reset_wait(self) -> None:
        self._reset_waiting = False

    def _write_log(self, message: str, level: str = "INFO") -> None:
        if self._log:
            self._log(message, level)
            return
        logger.log(getattr(logging, level, logging.INFO), message)

    @property
    def monitoring(self) -> bool:
        return self._monitoring

    @property
    def loaded(self) -> bool:
        return self._loaded

    def loading_status(self) -> str:
        if self._matched_port:
            return f"{self._matched_port} - Loading"
        return "Loading (no match)"

    def loaded_status(self) -> str:
        if self._matched_port:
            return f"{self._matched_port} - Loaded"
        return "Loaded"

    def record_match(self, management_port: int) -> None:
        self._matched_port = normalize_port_digits(management_port)
        if self._reset_waiting:
            return
        if self._monitoring and not self._loaded:
            self._write_log(self.loading_status())

    def forget_match(self) -> None:
        self._matched_port = None
        self._loaded = False
        self._reset_waiting = False

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._monitoring = False

    def _loading_sample(self) -> tuple[bool, float, float]:
        return self._screen.loading_bar_visible()

    def _log_loading_sample(self) -> bool:
        visible, dark_ratio, avg_lum = self._loading_sample()
        status = self.waiting_to_load_status() if self._reset_waiting else self.loading_status()
        self._write_log(
            f"{status} — loading bar "
            f"{'visible' if visible else 'not visible'} "
            f"(dark {dark_ratio * 100:.0f}%, avg lum {avg_lum:.0f})"
        )
        return visible

    async def _poll_until_loaded(
        self,
        *,
        deadline: float | None = None,
        emit_status: Callable[[str], Awaitable[None]] | None = None,
    ) -> bool:
        seen_loading = False
        started = time.monotonic()

        while True:
            if self._should_stop():
                return False
            if deadline is not None and time.monotonic() >= deadline:
                return False

            visible = self._log_loading_sample()
            if emit_status is not None:
                status = self.waiting_to_load_status() if self._reset_waiting else self.loading_status()
                await emit_status(status)

            elapsed = time.monotonic() - started
            if visible:
                seen_loading = True
            if seen_loading and not visible:
                return True
            if not seen_loading and not visible and elapsed >= NO_LOADING_SEEN_TIMEOUT_SECONDS:
                return True

            await asyncio.sleep(SCREEN_POLL_SECONDS)

    async def start(self, emit_status: Callable[[str], Awaitable[None]]) -> None:
        self.cancel()
        self._loaded = False
        self._matched_port = None
        self._reset_waiting = False
        self._monitoring = True
        self._task = asyncio.create_task(self._monitor(emit_status))

    async def wait_until_loaded(
        self,
        timeout: float = LOAD_WAIT_TIMEOUT_SECONDS,
        *,
        already_loaded_ok: bool = False,
    ) -> bool:
        if self._loaded:
            return True

        visible, _, _ = self._loading_sample()
        if already_loaded_ok and not self._reset_waiting and not visible and not self._monitoring:
            return True

        self._write_log("Waiting for loading bar to finish")
        deadline = time.monotonic() + timeout
        if await self._poll_until_loaded(deadline=deadline):
            self._loaded = True
            self._monitoring = False
            self._write_log(self.loaded_status())
            return True

        self._write_log("Timed out waiting for loading bar to finish", "ERROR")
        return False

    async def _monitor(self, emit_status: Callable[[str], Awaitable[None]]) -> None:
        try:
            if await self._poll_until_loaded(emit_status=emit_status):
                self._loaded = True
                self._monitoring = False
                self._write_log(self.loaded_status())
                await emit_status(self.loaded_status())
        except asyncio.CancelledError:
            raise
