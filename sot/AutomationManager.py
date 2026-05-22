import asyncio

import keyboard
import pyautogui
import pynput.mouse
import win32gui

SOT_WINDOW_MATCH = "sea of thieves"
IMAGE_CONFIDENCE = 0.9
SCREEN_POLL_SECONDS = 0.5


class AutomationManager:
    def __init__(self):
        self.stop = False
        self.ship = "Brigantine"
        self.holding = False

    def window_enumeration_handler(self, hwnd, top_windows):
        top_windows.append(
            (
                hwnd,
                win32gui.GetWindowText(hwnd),  # pylint: disable=c-extension-no-member
            )
        )

    def _find_sot_hwnd(self, window_match=SOT_WINDOW_MATCH):
        top_windows = []
        win32gui.EnumWindows(  # pylint: disable=c-extension-no-member
            self.window_enumeration_handler,
            top_windows,
        )
        for hwnd, title in top_windows:
            if window_match in title.lower() and win32gui.IsWindowVisible(hwnd):  # pylint: disable=c-extension-no-member
                return hwnd
        return None

    def _get_game_region(self):
        """Screen region (left, top, width, height) for the SoT window, or None."""
        hwnd = self._find_sot_hwnd()
        if not hwnd:
            return None
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)  # pylint: disable=c-extension-no-member
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None
        return (left, top, width, height)

    def locate_in_game(self, image_path, confidence=IMAGE_CONFIDENCE):
        """Find template image within the game window (full screen if window not found)."""
        region = self._get_game_region()
        kwargs = {"confidence": confidence}
        if region:
            kwargs["region"] = region
        return pyautogui.locateOnScreen(image_path, **kwargs)

    def screen_visible(self, image_path, confidence=IMAGE_CONFIDENCE):
        try:
            return self.locate_in_game(image_path, confidence) is not None
        except pyautogui.ImageNotFoundException:
            return False

    async def wait_for_screen(self, image_path, message=None, confidence=IMAGE_CONFIDENCE):
        while True:
            if self.screen_visible(image_path, confidence):
                return True
            if message:
                print(message)
            await asyncio.sleep(SCREEN_POLL_SECONDS)
            if self.stop:
                return False

    async def wait_for_play_screen(self):
        while True:
            if self.screen_visible("img/play_screen.png"):
                return True
            if self.screen_visible("img/rejoin_prompt.png"):
                await asyncio.sleep(0.5)
                keyboard.press_and_release("esc")
                print("Declined rejoin prompt")
            print("Waiting for play screen")
            await asyncio.sleep(SCREEN_POLL_SECONDS)
            if self.stop:
                return False

    async def dismiss_popup_if_visible(self, image_path):
        if self.screen_visible(image_path):
            keyboard.press_and_release("esc")
            await asyncio.sleep(0.5)
            print("Closed popup")

    def activate_window(self, window=SOT_WINDOW_MATCH):
        hwnd = self._find_sot_hwnd(window)
        if hwnd:
            win32gui.ShowWindow(hwnd, 5)  # pylint: disable=c-extension-no-member
            keyboard.press_and_release("alt")
            win32gui.SetForegroundWindow(hwnd)  # pylint: disable=c-extension-no-member

    async def set_ship(self, sio, ship_type):
        self.ship = ship_type
        await sio.emit("update_status", data=f"Ship set to {self.ship}")

    async def launch_game(self, sio, leave):
        await sio.emit("update_status", data="Launching Game")
        keyboard.press_and_release("win")
        await asyncio.sleep(2.5)
        keyboard.write("sea of thieves")
        await asyncio.sleep(1.5)
        keyboard.press_and_release("enter")
        await asyncio.sleep(1.5)
        await self.reset(sio, leave, portspiking=False)

    async def sail(self, sio, _portspike):
        self.activate_window()
        await asyncio.sleep(0.2)
        keyboard.press_and_release("enter")
        await sio.emit("update_status", data="Searching the seas")

    async def rejoin_session(self, sio, portspiking, port):
        if not port:
            await sio.emit("update_status", data="No previous session found")
            return
        if not portspiking:
            await sio.emit("update_status", data="Only available during portspike")
            return
        await sio.emit("update_status", data="Rejoining session")
        await asyncio.sleep(0.5)

        if not await self.wait_for_screen(
            "img/portspike_connected.png", "waiting for portspike client to connect"
        ):
            return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data="Awaiting rejoin prompt")
        if not await self.wait_for_screen("img/rejoin_prompt.png", "waiting for rejoin prompt"):
            return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data=f"Rejoining {port}")

    async def reset(self, sio, leave, portspiking):
        if portspiking:
            await sio.emit("update_status", data="Awaiting connection")
            if not await self.wait_for_screen(
                "img/portspike_connected.png", "waiting for portspike client to connect"
            ):
                return

            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            await sio.emit("update_status", data="Awaiting rejoin prompt")
            if not await self.wait_for_screen("img/rejoin_prompt.png", "waiting for rejoin prompt"):
                return

            keyboard.press_and_release("esc")
        elif leave:
            await sio.emit("update_status", data="Leaving Game")
            self.activate_window()
            await asyncio.sleep(0.2)
            keyboard.press_and_release("esc")
            await asyncio.sleep(1.2)
            for _ in range(7):
                keyboard.press_and_release("down")
                await asyncio.sleep(0.3)
            keyboard.press_and_release("up")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")

        if not portspiking:
            if not await self.wait_for_screen("img/start_screen.png", "Waiting for start screen"):
                return

            await sio.emit("update_status", data="Starting Game")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")

        if not await self.wait_for_play_screen():
            return

        await sio.emit("update_status", data="Waiting for the popup")
        await asyncio.sleep(3)

        await self.dismiss_popup_if_visible("img/stupid_popup_1.png")
        await self.dismiss_popup_if_visible("img/stupid_popup_2.png")

        await sio.emit("update_status", data="Selecting gamemode")
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("right")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)

        print(self.ship)
        await sio.emit("update_status", data="Selecting ship")
        if self.ship == "Captaincy":
            keyboard.press_and_release("right")
            await asyncio.sleep(0.6)
            if not await self.wait_for_screen(
                "img/captaincy_available.png", "Waiting for captaincy to load"
            ):
                return

            keyboard.press_and_release("enter")
            if not await self.wait_for_screen(
                "img/ship_loaded.png", "Waiting for captaincy ship to load"
            ):
                return
        else:
            keyboard.press_and_release("enter")

        if self.ship == "Brigantine":
            keyboard.press_and_release("down")
        elif self.ship == "Sloop":
            keyboard.press_and_release("down")
            await asyncio.sleep(0.6)
            keyboard.press_and_release("down")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await sio.emit("update_status", data="Confirming crew")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")

        if not await self.wait_for_screen("img/sail_screen.png", "Waiting for sail screen"):
            return

        await sio.emit("update_status", data="Ready")
        print("waiting on set sail screen")

    async def kill_game(self, sio):
        await sio.emit("update_status", data="Killing Game")
        self.activate_window()
        await asyncio.sleep(0.2)
        mouse = pynput.mouse.Controller()
        mouse.click(pynput.mouse.Button.left, 2)
        await asyncio.sleep(0.5)
        keyboard.press_and_release("alt+f4")

    async def stop_functions(self, sio):
        await sio.emit("update_status", data="Stopping functions")
        self.stop = True
        await asyncio.sleep(2.5)
        self.stop = False
        await sio.emit("update_status", data="No longer stopping functions")
        await asyncio.sleep(2.5)
        await sio.emit("update_status", data="Pending...")

    async def auto_hold(self, sio):
        await sio.emit("update_status", data="(AH) Waiting for hold requests.")
        if self.holding:
            await sio.emit("update_status", data="(AH) Already holding.")
            await sio.emit("hold_request_ack", data="Already holding.")
            return

        self.holding = False

    async def hold_request(self, sio):
        if self.holding:
            await sio.emit("update_status", data="(AH) Already holding.")
            await sio.emit("hold_request_ack", data="Already holding.")
            return

        await sio.emit("update_status", data="(AH) Request Received.")
        await sio.emit("hold_request_ack", data="Request Received.")
        self.holding = True
        await asyncio.sleep(20)
        await sio.emit("update_status", data="(AH) Holding a ship.")

    async def invite_request(self, sio, person_to_invite):
        await sio.emit("update_status", data=f"Inviting {person_to_invite}")
        self.activate_window()
        await asyncio.sleep(0.2)

        print("Starting Xbox App")
        keyboard.press_and_release("win")
        await asyncio.sleep(2.5)
        keyboard.write("xbox")
        await asyncio.sleep(1.5)
        keyboard.press_and_release("enter")
        print("Xbox App Started")
        await asyncio.sleep(30)
        print("opening friends tab")
        # 9 tabs to get to the friends tab #!! 11 on main pc
        for _ in range(9):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        keyboard.press_and_release("enter")
        print("Friends tab opened")
        await asyncio.sleep(1)
        print("searching for user")
        for _ in range(2):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        keyboard.write(person_to_invite)
        await asyncio.sleep(2.5)
        keyboard.press_and_release("enter")
        print("User found")
        await asyncio.sleep(6)
        print("Getting to invite button")
        for _ in range(5):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        keyboard.press_and_release("shift+f10")
        await asyncio.sleep(1)
        keyboard.press_and_release("shift+tab")
        await asyncio.sleep(0.5)
        keyboard.press_and_release("shift+tab")
        await asyncio.sleep(0.5)
        print("Inviting user")
        keyboard.press_and_release("enter")
        await asyncio.sleep(1)
        print("User invited")
        await sio.emit("update_status", data=f"Invited {person_to_invite}")
