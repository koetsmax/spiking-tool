"""Expandable periodic health checks for the spiking-tool client."""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from sot.ui_automation import GameScreenMatcher

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_SECONDS = 60.0
VIDEO_DRIVER_CRASH_IMAGE = "img/video_driver_crashed.png"

FailureCallback = Callable[["PeriodicCheckResult"], Awaitable[None]]
ShouldRunCallback = Callable[[], bool]


@dataclass(frozen=True)
class PeriodicCheckResult:
    check_id: str
    ok: bool
    message: str = ""
    level: str = "WARNING"


@dataclass
class PeriodicCheckContext:
    screen: GameScreenMatcher
    on_failure: FailureCallback
    should_run: ShouldRunCallback
    log: Callable[[str, str], None]


class PeriodicCheck(ABC):
    """One recurring check; subclass and register with :class:`PeriodicCheckRunner`."""

    @property
    @abstractmethod
    def check_id(self) -> str:
        ...

    @property
    def interval_seconds(self) -> float:
        return DEFAULT_CHECK_INTERVAL_SECONDS

    @abstractmethod
    async def run(self, context: PeriodicCheckContext) -> PeriodicCheckResult:
        ...


class GameRunningCheck(PeriodicCheck):
    """Verify SoTGame.exe is running and the main game window exists."""

    def __init__(self, screen: GameScreenMatcher) -> None:
        self._screen = screen

    @property
    def check_id(self) -> str:
        return "game_running"

    async def run(self, context: PeriodicCheckContext) -> PeriodicCheckResult:
        del context
        if not self._screen.sotgame_running():
            return PeriodicCheckResult(
                check_id=self.check_id,
                ok=False,
                message="Sea of Thieves is not running (sotgame.exe not found)",
                level="ERROR",
            )
        if self._screen.find_sot_hwnd() is None:
            return PeriodicCheckResult(
                check_id=self.check_id,
                ok=False,
                message="Sea of Thieves process is running but the game window was not found",
                level="ERROR",
            )
        return PeriodicCheckResult(check_id=self.check_id, ok=True)


class VideoDriverCrashedCheck(PeriodicCheck):
    """
    Detect the GPU driver crash dialog via template match on the full desktop.

    The crash popup is a separate window, not inside the SoT client region.
    Add a screenshot as ``img/video_driver_crashed.png``.
    """

    def __init__(
        self,
        screen: GameScreenMatcher,
        *,
        image_path: str = VIDEO_DRIVER_CRASH_IMAGE,
    ) -> None:
        self._screen = screen
        self._image_path = image_path
        self._logged_missing_image = False

    @property
    def check_id(self) -> str:
        return "video_driver_crashed"

    async def run(self, context: PeriodicCheckContext) -> PeriodicCheckResult:
        del context
        if not os.path.isfile(self._image_path):
            if not self._logged_missing_image:
                self._logged_missing_image = True
                logger.warning(
                    "Video driver crash check disabled — add template at %s",
                    self._image_path,
                )
            return PeriodicCheckResult(check_id=self.check_id, ok=True)
        if self._screen.screen_visible_on_desktop(self._image_path):
            return PeriodicCheckResult(
                check_id=self.check_id,
                ok=False,
                message="Video driver crashed screen detected",
                level="ERROR",
            )
        return PeriodicCheckResult(check_id=self.check_id, ok=True)


def default_periodic_checks(screen: GameScreenMatcher) -> list[PeriodicCheck]:
    """Built-in checks; append custom :class:`PeriodicCheck` subclasses when registering."""
    return [
        GameRunningCheck(screen),
        VideoDriverCrashedCheck(screen),
    ]


class PeriodicCheckRunner:
    """Runs registered checks on independent intervals."""

    def __init__(
        self,
        checks: list[PeriodicCheck],
        *,
        context: PeriodicCheckContext,
    ) -> None:
        self._checks = list(checks)
        self._context = context
        self._tasks: list[asyncio.Task] = []
        self._last_failure_key: dict[str, str] = {}
        self._shutdown_requested = False

    def register(self, check: PeriodicCheck) -> None:
        self._checks.append(check)

    @property
    def check_ids(self) -> list[str]:
        return [check.check_id for check in self._checks]

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def request_shutdown(self) -> None:
        self._shutdown_requested = True

    def start(self) -> None:
        if self._tasks:
            return
        for check in self._checks:
            self._tasks.append(asyncio.create_task(self._loop(check), name=f"periodic-{check.check_id}"))

    async def stop(self) -> None:
        self.request_shutdown()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _loop(self, check: PeriodicCheck) -> None:
        await asyncio.sleep(0.5)
        was_afk_active = False
        while not self._shutdown_requested:
            if not self._context.should_run():
                if was_afk_active:
                    self._context.log(f"{check.check_id}: paused (anti-AFK off)", "INFO")
                was_afk_active = False
                self._last_failure_key.pop(check.check_id, None)
                await self._wait_or_stop(1.0)
                continue

            if not was_afk_active:
                was_afk_active = True
                self._last_failure_key.pop(check.check_id, None)
                self._context.log(f"{check.check_id}: resumed (anti-AFK on)", "INFO")

            try:
                result = await check.run(self._context)
                if not result.ok:
                    await self._handle_failure(result)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Periodic check %s failed", check.check_id)
            try:
                await asyncio.wait_for(
                    self._wait_or_stop(check.interval_seconds),
                    timeout=check.interval_seconds + 1.0,
                )
            except asyncio.CancelledError:
                raise

    async def _wait_or_stop(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds and not self._shutdown_requested:
            sleep_for = min(1.0, seconds - elapsed)
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for

    async def _handle_failure(self, result: PeriodicCheckResult) -> None:
        dedupe_key = f"{result.check_id}:{result.message}"
        if self._last_failure_key.get(result.check_id) == dedupe_key:
            return
        self._last_failure_key[result.check_id] = dedupe_key
        await self._context.on_failure(result)
