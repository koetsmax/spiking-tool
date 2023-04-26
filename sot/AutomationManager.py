from win32gui import *
import psutil
import keyboard
import time
import win32gui

import pyautogui
import asyncio
import pynput.mouse


class AutomationManager:
    def window_enumeration_handler(self, hwnd, top_windows):
        """
        Function that gets all the windows and adds them to a list
        """
        top_windows.append(
            (
                hwnd,
                win32gui.GetWindowText(hwnd),  # pylint: disable=c-extension-no-member
            )
        )

    def activate_window(self, window):
        """
        Function that tries to activate the Sea of Thieves window
        """
        top_windows = []
        win32gui.EnumWindows(  # pylint: disable=c-extension-no-member
            self.window_enumeration_handler,  # pylint: disable=c-extension-no-member
            top_windows,
        )
        for i in top_windows:
            if window in i[1].lower():
                win32gui.ShowWindow(i[0], 5)  # pylint: disable=c-extension-no-member
                keyboard.press_and_release("alt")
                win32gui.SetForegroundWindow(  # pylint: disable=c-extension-no-member
                    i[0]
                )
                break

    async def launch_game(self, sio, ship_type, leave):
        """
        Function that launches the game and gets the client to the set sail screen
        """
        await sio.emit("update_status", data="Launching Game")
        keyboard.press_and_release("win")
        await asyncio.sleep(2.5)
        keyboard.write("sea of thieves")
        await asyncio.sleep(1.5)
        keyboard.press_and_release("enter")
        await asyncio.sleep(1.5)
        await self.reset(sio, ship_type, leave, portspiking=False)

    async def sail(self, sio):
        self.activate_window("sea of thieves")
        time.sleep(0.2)
        keyboard.press_and_release("enter")
        await sio.emit("update_status", data="Searching the seas")

    async def reset(self, sio, ship_type, leave, portspiking):
        if portspiking:
            while not pyautogui.locateOnScreen(
                "img/portspike_connected.png", confidence=0.9
            ):
                await asyncio.sleep(0.5)
                print("waiting for portspike client to connect")
            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            while not pyautogui.locateOnScreen("img/rejoin_prompt.png", confidence=0.9):
                await asyncio.sleep(0.5)
                print("waiting for rejoin prompt")
            keyboard.press_and_release("esc")
        elif leave:
            # Leave game
            await sio.emit("update_status", data="Leaving Game")
            self.activate_window("sea of thieves")
            await asyncio.sleep(0.2)
            keyboard.press_and_release("esc")
            await asyncio.sleep(1)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")
        if not portspiking:
            # start game
            while not pyautogui.locateOnScreen("img/start_screen.png", confidence=0.9):
                print("Waiting for start screen")
                await asyncio.sleep(0.5)
            await sio.emit("update_status", data="Starting Game")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")

        # start menuing
        while not pyautogui.locateOnScreen("img/play_screen.png", confidence=0.9):
            print("Waiting for play screen")
            await asyncio.sleep(0.5)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("right")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)

        # select ship
        print(ship_type)
        await sio.emit("update_status", data="Selecting ship")
        if ship_type == "Captaincy":
            keyboard.press_and_release("right")
            await asyncio.sleep(0.3)
            while not pyautogui.locateOnScreen(
                "img/captaincy_available.png", confidence=0.9
            ):
                print("Waiting for captaincy to load")
                await asyncio.sleep(0.5)
            keyboard.press_and_release("enter")
            while not pyautogui.locateOnScreen("img/ship_loaded.png", confidence=0.9):
                print("Waiting for captaincy ship to load")
                await asyncio.sleep(0.5)
        elif ship_type == "Brigantine":
            keyboard.press_and_release("down")
        elif ship_type == "Sloop":
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("down")
        await asyncio.sleep(0.3)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        keyboard.press_and_release("enter")

        # get to set sail screen
        while not pyautogui.locateOnScreen("img/sail_screen.png", confidence=0.9):
            print("Waiting for sail screen")
            await asyncio.sleep(0.5)
        await sio.emit("update_status", data="Ready")
        print("waiting on set sail screen")

    async def kill_game(self, sio):
        """
        Function that kills the game
        """
        await sio.emit("update_status", data="Killing Game")
        self.activate_window("sea of thieves")
        await asyncio.sleep(0.2)
        mouse = pynput.mouse.Controller()
        mouse.click(pynput.mouse.Button.left, 2)
        await asyncio.sleep(0.2)
        keyboard.press_and_release("alt+f4")
