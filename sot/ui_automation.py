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

SOTGAME_PROCESS = "sotgame.exe"
# EAC bootstrapper parent process (not the game — the game is SoTGame.exe).
BOOTSTRAPPER_PROCESS = "seaofthieves.exe"
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
            return f"Resized to 800x600 (was {self.previous_width}x{self.previous_height})"
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
    def _process_running(process_name: str) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info.get("name", "").lower() == process_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    @staticmethod
    def sotgame_pids() -> set[int]:
        pids: set[int] = set()
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if proc.info.get("name", "").lower() == SOTGAME_PROCESS:
                    pids.add(int(proc.info["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
                continue
        return pids

    @staticmethod
    def should_skip_resize() -> bool:
        """Skip while the EAC bootstrapper is still running or the game has not started."""
        if GameScreenMatcher._process_running(BOOTSTRAPPER_PROCESS):
            return True
        return not GameScreenMatcher.sotgame_running()

    def wait_until_ready_to_resize(
        self,
        timeout_seconds: float = 120.0,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self.should_skip_resize() and self.find_sot_hwnd() is not None:
                return True
            if self._should_stop():
                return False
            time.sleep(0.5)
        return False

    def find_sot_hwnd(self):
        """Return the main top-level window owned by SoTGame.exe."""
        game_pids = self.sotgame_pids()
        if not game_pids:
            return None

        candidates: list[tuple[int, int, bool]] = []

        def callback(hwnd, _extra) -> bool:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)  # pylint: disable=c-extension-no-member
            if pid not in game_pids:
                return True
            if not win32gui.IsWindow(hwnd):  # pylint: disable=c-extension-no-member
                return True
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)  # pylint: disable=c-extension-no-member
            if style & win32con.WS_CHILD:
                return True
            width, height = self.get_client_size(hwnd)
            if width < 100 or height < 100:
                return True
            candidates.append(
                (hwnd, width * height, bool(win32gui.IsWindowVisible(hwnd)))  # pylint: disable=c-extension-no-member
            )
            return True

        win32gui.EnumWindows(callback, None)  # pylint: disable=c-extension-no-member
        if not candidates:
            logger.debug("No top-level windows found for %s (pids=%s)", SOTGAME_PROCESS, game_pids)
            return None

        visible = [candidate for candidate in candidates if candidate[2]]
        pool = visible or candidates
        return max(pool, key=lambda candidate: candidate[1])[0]

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
        if self.should_skip_resize():
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

        if self.should_skip_resize():
            logger.debug("Skipping resize until SoTGame.exe is ready")
            return ResolutionCheckResult(status="no_window")

        hwnd = self.find_sot_hwnd()
        if hwnd is None:
            return ResolutionCheckResult(status="no_window")
        width, height = check.width, check.height
        previous_width, previous_height = width, height
        logger.info(
            "Resizing SoTGame window from %sx%s to %sx%s",
            previous_width,
            previous_height,
            target_width,
            target_height,
        )

        def resize_window() -> Tuple[int, int]:
            outer_width, outer_height = self._outer_size_for_client(hwnd, target_width, target_height)
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

    async def wait_for_screen(self, image_path: str, message: Optional[str] = None, confidence: float = IMAGE_CONFIDENCE) -> bool:
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
            if not promo_video_dismissed and time.monotonic() - wait_started_at >= promo_skip_after_seconds:
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

    def activate_window(self) -> None:
        hwnd = self.find_sot_hwnd()
        if hwnd:
            win32gui.ShowWindow(hwnd, 5)  # pylint: disable=c-extension-no-member
            keyboard.press_and_release("alt")
            win32gui.SetForegroundWindow(hwnd)  # pylint: disable=c-extension-no-member
