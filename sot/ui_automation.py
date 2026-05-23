from __future__ import annotations

import asyncio
from typing import Callable, Optional, Tuple

import keyboard
import pyautogui
import win32gui

SOT_WINDOW_MATCH = "sea of thieves"
IMAGE_CONFIDENCE = 0.9
SCREEN_POLL_SECONDS = 0.5

GameRegion = Tuple[int, int, int, int]


class GameScreenMatcher:
    """Template matching and window focus helpers scoped to the SoT game window."""

    def __init__(self, should_stop: Optional[Callable[[], bool]] = None) -> None:
        self._should_stop = should_stop or (lambda: False)

    @staticmethod
    def _window_enumeration_handler(hwnd, top_windows) -> None:
        top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))  # pylint: disable=c-extension-no-member

    def find_sot_hwnd(self, window_match: str = SOT_WINDOW_MATCH):
        top_windows = []
        win32gui.EnumWindows(self._window_enumeration_handler, top_windows)  # pylint: disable=c-extension-no-member
        for hwnd, title in top_windows:
            if window_match in title.lower() and win32gui.IsWindowVisible(hwnd):  # pylint: disable=c-extension-no-member
                return hwnd
        return None

    def get_game_region(self) -> Optional[GameRegion]:
        hwnd = self.find_sot_hwnd()
        if not hwnd:
            return None
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)  # pylint: disable=c-extension-no-member
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None
        return (left, top, width, height)

    def locate_in_game(self, image_path: str, confidence: float = IMAGE_CONFIDENCE):
        region = self.get_game_region()
        kwargs = {"confidence": confidence}
        if region:
            kwargs["region"] = region
        return pyautogui.locateOnScreen(image_path, **kwargs)

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

    async def wait_for_play_screen(self) -> bool:
        while True:
            if self.screen_visible("img/play_screen.png"):
                return True
            if self.screen_visible("img/rejoin_prompt.png"):
                await asyncio.sleep(0.5)
                keyboard.press_and_release("esc")
                print("Declined rejoin prompt")
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
