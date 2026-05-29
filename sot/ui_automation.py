from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, Optional, Tuple

import keyboard
import psutil
import pyautogui
import win32con
import win32gui
import win32process

logger = logging.getLogger(__name__)

SOT_WINDOW_MATCH = "sea of thieves"
SOTGAME_PROCESS = "sotgame.exe"
EAC_PROCESS_PREFIX = "easyanticheat"
EAC_WAIT_POLL_SECONDS = 0.5
EAC_WAIT_TIMEOUT_SECONDS = 300.0
GAME_CLOSE_POLL_SECONDS = 0.5
GAME_CLOSE_TIMEOUT_SECONDS = 30.0
IMAGE_CONFIDENCE = 0.9
SCREEN_POLL_SECONDS = 0.5
PROMO_VIDEO_SKIP_SECONDS = 30.0
PROMO_VIDEO_ESC_GAP_SECONDS = 0.5
TARGET_CLIENT_WIDTH = 800
TARGET_CLIENT_HEIGHT = 600

GameRegion = Tuple[int, int, int, int]

ResolutionStatus = Literal["ok", "resized", "failed", "no_window"]


@dataclass(frozen=True)
class ResolutionCheckResult:
    status: ResolutionStatus
    width: int = 0
    height: int = 0
    previous_width: int = 0
    previous_height: int = 0

    @property
    def status_message(self) -> str:
        if self.status == "ok":
            return "Resolution OK (800x600)"
        if self.status == "resized":
            return (
                f"Resized to 800x600 (was {self.previous_width}x{self.previous_height})"
            )
        if self.status == "no_window":
            return "SoT window not found"
        return f"Wrong resolution {self.width}x{self.height} (need 800x600)"


class GameScreenMatcher:
    """Template matching and window focus helpers scoped to the SoT game window."""

    def __init__(self, should_stop: Optional[Callable[[], bool]] = None) -> None:
        self._should_stop = should_stop or (lambda: False)

    @staticmethod
    def _window_enumeration_handler(hwnd, top_windows) -> None:
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))  # pylint: disable=c-extension-no-member

    @staticmethod
    def _hwnd_process_name(hwnd) -> Optional[str]:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)  # pylint: disable=c-extension-no-member
            return psutil.Process(pid).name().lower()
        except (psutil.Error, OSError, ValueError):
            return None

    @staticmethod
    def _is_eac_launcher(hwnd) -> bool:
        process_name = GameScreenMatcher._hwnd_process_name(hwnd)
        if not process_name:
            return False
        return process_name.startswith(EAC_PROCESS_PREFIX)

    @staticmethod
    def eac_launcher_visible() -> bool:
        top_windows = []
        win32gui.EnumWindows(GameScreenMatcher._window_enumeration_handler, top_windows)  # pylint: disable=c-extension-no-member
        for hwnd, _title in top_windows:
            if not win32gui.IsWindowVisible(hwnd):  # pylint: disable=c-extension-no-member
                continue
            if GameScreenMatcher._is_eac_launcher(hwnd):
                return True
        return False

    def wait_for_eac_launcher_gone(
        self,
        timeout_seconds: float = EAC_WAIT_TIMEOUT_SECONDS,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.eac_launcher_visible():
                return True
            if self._should_stop():
                return False
            time.sleep(EAC_WAIT_POLL_SECONDS)
        logger.warning("Timed out waiting for EAC launcher to close")
        return False

    def find_sot_hwnd(self, window_match: str = SOT_WINDOW_MATCH):
        top_windows = []
        win32gui.EnumWindows(self._window_enumeration_handler, top_windows)  # pylint: disable=c-extension-no-member
        title_match = None
        for hwnd, title in top_windows:
            if not win32gui.IsWindowVisible(hwnd):  # pylint: disable=c-extension-no-member
                continue
            process_name = self._hwnd_process_name(hwnd)
            if process_name == SOTGAME_PROCESS:
                return hwnd
            if window_match in title.lower() and not self._is_eac_launcher(hwnd):
                title_match = hwnd
        return title_match

    def _wait_for_game_window_before_resize(self) -> bool:
        if not self.eac_launcher_visible():
            return True
        logger.info("Waiting for EAC launcher to close before resizing the game window")
        return self.wait_for_eac_launcher_gone()

    @staticmethod
    def sotgame_running() -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info.get("name", "").lower() == SOTGAME_PROCESS:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def find_sotgame_pid(self) -> Optional[int]:
        hwnd = self.find_sot_hwnd()
        if hwnd:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)  # pylint: disable=c-extension-no-member
            return pid

        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info.get("name", "").lower() == SOTGAME_PROCESS:
                    return int(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
                continue
        return None

    def post_wm_close_to_pid(self, pid: int) -> int:
        sent = 0

        def callback(hwnd, _extra) -> bool:
            nonlocal sent
            if not win32gui.IsWindowVisible(hwnd):  # pylint: disable=c-extension-no-member
                return True
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)  # pylint: disable=c-extension-no-member
            if found_pid == pid:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # pylint: disable=c-extension-no-member
                sent += 1
            return True

        win32gui.EnumWindows(callback, None)  # pylint: disable=c-extension-no-member
        return sent

    def wait_for_sotgame_exit(
        self,
        timeout_seconds: float = GAME_CLOSE_TIMEOUT_SECONDS,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.sotgame_running():
                return True
            if self._should_stop():
                return False
            time.sleep(GAME_CLOSE_POLL_SECONDS)
        return False

    def request_close_game(
        self,
        timeout_seconds: float = GAME_CLOSE_TIMEOUT_SECONDS,
    ) -> bool:
        """
        Ask the game to close via WM_CLOSE (same as clicking the window X button).

        psutil is only used to detect when sotgame.exe has exited; terminate()/kill()
        are not used because they force-kill without running the game's shutdown path.
        """
        pid = self.find_sotgame_pid()
        if pid is None:
            logger.info("No %s process found to close", SOTGAME_PROCESS)
            return True

        windows_closed = 0
        hwnd = self.find_sot_hwnd()
        if hwnd:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # pylint: disable=c-extension-no-member
            windows_closed += 1
        windows_closed += self.post_wm_close_to_pid(pid)
        if windows_closed == 0:
            logger.warning("No visible game windows found for pid %s", pid)
            return False

        logger.info("Requested game close via WM_CLOSE (pid=%s)", pid)
        return self.wait_for_sotgame_exit(timeout_seconds)

    @staticmethod
    def get_client_size(hwnd) -> Tuple[int, int]:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)  # pylint: disable=c-extension-no-member
        return right - left, bottom - top

    @staticmethod
    def _outer_size_for_client(hwnd, client_width: int, client_height: int) -> Tuple[int, int]:
        """Map desired client size to outer window size using current window chrome."""
        window_left, window_top, window_right, window_bottom = win32gui.GetWindowRect(hwnd)  # pylint: disable=c-extension-no-member
        client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)  # pylint: disable=c-extension-no-member
        screen_left, screen_top = win32gui.ClientToScreen(hwnd, (client_left, client_top))  # pylint: disable=c-extension-no-member
        screen_right, screen_bottom = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))  # pylint: disable=c-extension-no-member
        chrome_width = (window_right - window_left) - (screen_right - screen_left)
        chrome_height = (window_bottom - window_top) - (screen_bottom - screen_top)
        return client_width + chrome_width, client_height + chrome_height

    def check_target_resolution(
        self,
        target_width: int = TARGET_CLIENT_WIDTH,
        target_height: int = TARGET_CLIENT_HEIGHT,
    ) -> ResolutionCheckResult:
        if self.eac_launcher_visible():
            return ResolutionCheckResult(status="no_window")

        hwnd = self.find_sot_hwnd()
        if not hwnd:
            return ResolutionCheckResult(status="no_window")

        width, height = self.get_client_size(hwnd)
        if width == target_width and height == target_height:
            return ResolutionCheckResult(status="ok", width=width, height=height)
        return ResolutionCheckResult(
            status="failed",
            width=width,
            height=height,
        )

    def ensure_target_resolution(
        self,
        target_width: int = TARGET_CLIENT_WIDTH,
        target_height: int = TARGET_CLIENT_HEIGHT,
    ) -> ResolutionCheckResult:
        check = self.check_target_resolution(target_width, target_height)
        if check.status in ("ok", "no_window"):
            return check

        if not self._wait_for_game_window_before_resize():
            return ResolutionCheckResult(status="no_window")

        hwnd = self.find_sot_hwnd()
        assert hwnd is not None
        width, height = check.width, check.height
        previous_width, previous_height = width, height

        def resize_window() -> Tuple[int, int]:
            outer_width, outer_height = self._outer_size_for_client(
                hwnd, target_width, target_height
            )
            win32gui.SetWindowPos(  # pylint: disable=c-extension-no-member
                hwnd,
                win32con.HWND_TOP,
                0,
                0,
                outer_width,
                outer_height,
                win32con.SWP_SHOWWINDOW,
            )
            return self.get_client_size(hwnd)

        width, height = resize_window()
        if width == target_width and height == target_height:
            logger.info(
                "Resized SoT window from %sx%s to %sx%s",
                previous_width,
                previous_height,
                width,
                height,
            )
            return ResolutionCheckResult(
                status="resized",
                width=width,
                height=height,
                previous_width=previous_width,
                previous_height=previous_height,
            )

        if width > target_width * 2 or height > target_height * 2:
            logger.info(
                "Client area %sx%s looks fullscreen; toggling with Alt+Enter before resize",
                width,
                height,
            )
            keyboard.press_and_release("alt+enter")
            time.sleep(2.0)
            width, height = resize_window()

        if width == target_width and height == target_height:
            logger.info(
                "Resized SoT window from %sx%s to %sx%s (after leaving fullscreen)",
                previous_width,
                previous_height,
                width,
                height,
            )
            return ResolutionCheckResult(
                status="resized",
                width=width,
                height=height,
                previous_width=previous_width,
                previous_height=previous_height,
            )

        logger.warning(
            "SoT window is %sx%s; expected %sx%s after resize attempt",
            width,
            height,
            target_width,
            target_height,
        )
        return ResolutionCheckResult(
            status="failed",
            width=width,
            height=height,
            previous_width=previous_width,
            previous_height=previous_height,
        )

    def get_game_client_region(self) -> Optional[GameRegion]:
        """Screen-space client area (matches 800x600 template captures)."""
        hwnd = self.find_sot_hwnd()
        if not hwnd:
            return None
        left, top, right, bottom = win32gui.GetClientRect(hwnd)  # pylint: disable=c-extension-no-member
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None
        screen_left, screen_top = win32gui.ClientToScreen(hwnd, (left, top))  # pylint: disable=c-extension-no-member
        return (screen_left, screen_top, width, height)

    def locate_in_game(self, image_path: str, confidence: float = IMAGE_CONFIDENCE):
        region = self.get_game_client_region()
        kwargs: dict = {"confidence": confidence}
        if region:
            kwargs["region"] = region
        try:
            return pyautogui.locateOnScreen(image_path, **kwargs)
        except ValueError:
            logger.warning(
                "Template %s does not fit game client region %s (wrong resolution or fullscreen)",
                image_path,
                region,
            )
            return None

    def screen_visible(self, image_path: str, confidence: float = IMAGE_CONFIDENCE) -> bool:
        try:
            return self.locate_in_game(image_path, confidence) is not None
        except pyautogui.ImageNotFoundException:
            return False

    async def wait_for_screen(
        self, image_path: str, message: Optional[str] = None, confidence: float = IMAGE_CONFIDENCE
    ) -> bool:
        while True:
            if self.screen_visible(image_path, confidence):
                return True
            if message:
                print(message)
            await asyncio.sleep(SCREEN_POLL_SECONDS)
            if self._should_stop():
                return False

    async def _dismiss_promo_video(self) -> None:
        """Skip new-content promo videos (no stable image to match)."""
        logger.info("No play screen after %.0fs; sending double Esc", PROMO_VIDEO_SKIP_SECONDS)
        keyboard.press_and_release("esc")
        await asyncio.sleep(PROMO_VIDEO_ESC_GAP_SECONDS)
        keyboard.press_and_release("esc")

    async def wait_for_play_screen(
        self,
        promo_skip_after_seconds: float = PROMO_VIDEO_SKIP_SECONDS,
        on_promo_skipped: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> bool:
        wait_started_at = time.monotonic()
        promo_video_dismissed = False
        while True:
            if self.screen_visible("img/play_screen.png"):
                return True
            if self.screen_visible("img/rejoin_prompt.png"):
                await asyncio.sleep(0.5)
                keyboard.press_and_release("esc")
                print("Declined rejoin prompt")
            if (
                not promo_video_dismissed
                and time.monotonic() - wait_started_at >= promo_skip_after_seconds
            ):
                await self._dismiss_promo_video()
                promo_video_dismissed = True
                if on_promo_skipped:
                    await on_promo_skipped()
            print("Waiting for play screen")
            await asyncio.sleep(SCREEN_POLL_SECONDS)
            if self._should_stop():
                return False

    async def dismiss_popup_if_visible(self, image_path: str) -> None:
        if self.screen_visible(image_path):
            keyboard.press_and_release("esc")
            await asyncio.sleep(0.5)
            print("Closed popup")

    def activate_window(self, window_match: str = SOT_WINDOW_MATCH) -> None:
        hwnd = self.find_sot_hwnd(window_match)
        if hwnd:
            win32gui.ShowWindow(hwnd, 5)  # pylint: disable=c-extension-no-member
            keyboard.press_and_release("alt")
            win32gui.SetForegroundWindow(hwnd)  # pylint: disable=c-extension-no-member
