import keyboard
import win32gui
import threading
import pyautogui
import asyncio
import pynput.mouse
import pyscreeze


class AutomationManager:
    def __init__(self):
        self.stop = False
        self.ship = "Brigantine"
        self.holding = False

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

        # first try to minimize the client window
        for i in top_windows:
            if "client.exe" in i[1].lower():
                win32gui.ShowWindow(i[0], 6)
                break

        for i in top_windows:
            if window in i[1].lower():
                win32gui.ShowWindow(i[0], 5)  # pylint: disable=c-extension-no-member
                keyboard.press_and_release("alt")
                win32gui.SetForegroundWindow(i[0])  # pylint: disable=c-extension-no-member
                break

    async def set_ship(self, sio, ship_type):
        """
        Function that sets the ship type
        """
        self.ship = ship_type
        await sio.emit("update_status", data=f"Ship set to {self.ship}")

    async def launch_game(self, sio, leave):
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
        await self.reset(sio, leave, portspiking=False)

    async def sail(self, sio, portspike):
        self.activate_window("sea of thieves")
        await asyncio.sleep(0.2)
        keyboard.press_and_release("enter")
        await sio.emit("update_status", data="Searching the seas")
        # if not portspike:
        #     while not pyautogui.locateOnScreen("img/loading.png", confidence=0.9):
        #         await asyncio.sleep(0.5)
        #         print("black screen not found")
        #         if self.stop:
        #             return

        #     await sio.emit("update_status", data="Loading...")

        #     while pyautogui.locateOnScreen("img/loading.png", confidence=0.9):
        #         await asyncio.sleep(0.5)
        #         print("black screen found")
        #         if self.stop:
        #             return
        #     await sio.emit("update_status", data="Loaded")
        #     print("loaded")

    async def rejoin_session(self, sio, portspiking, port):
        if not port:
            await sio.emit("update_status", data="No previous session found")
            return
        if not portspiking:
            await sio.emit("update_status", data="Only available during portspike")
            return
        await sio.emit("update_status", data="Rejoining session")
        await asyncio.sleep(0.5)

        while True:
            try:
                if pyautogui.locateOnScreen("img/portspike_connected.png", confidence=0.9):
                    break
            except pyautogui.ImageNotFoundException:
                pass

            await asyncio.sleep(0.5)
            print("waiting for portspike client to connect")

            if self.stop:
                return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data="Awaiting rejoin prompt")
        while True:
            try:
                if pyautogui.locateOnScreen("img/rejoin_prompt.png", confidence=0.9):
                    break
            except pyautogui.ImageNotFoundException:
                pass

            await asyncio.sleep(0.5)
            print("waiting for rejoin prompt")

            if self.stop:
                return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data=f"Rejoining {port}")

    async def reset(self, sio, leave, portspiking):
        if portspiking:
            await sio.emit("update_status", data="Awaiting connection")
            while True:
                try:
                    if pyautogui.locateOnScreen("img/portspike_connected.png", confidence=0.9):
                        break
                except pyautogui.ImageNotFoundException:
                    pass

                await asyncio.sleep(0.5)
                print("waiting for portspike client to connect")

                if self.stop:
                    return

            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            await sio.emit("update_status", data="Awaiting rejoin prompt")
            while True:
                try:
                    if pyautogui.locateOnScreen("img/rejoin_prompt.png", confidence=0.9):
                        break
                except pyautogui.ImageNotFoundException:
                    pass

                await asyncio.sleep(0.5)
                print("waiting for rejoin prompt")

                if self.stop:
                    return
            keyboard.press_and_release("esc")
        elif leave:
            # Leave game
            await sio.emit("update_status", data="Leaving Game")
            self.activate_window("sea of thieves")
            await asyncio.sleep(0.2)
            keyboard.press_and_release("esc")
            await asyncio.sleep(1.2)
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
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("up")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")
        if not portspiking:
            # start game
            while True:
                try:
                    if pyautogui.locateOnScreen("img/start_screen.png", confidence=0.9):
                        break
                except pyautogui.ImageNotFoundException:
                    pass

                print("Waiting for start screen")
                await asyncio.sleep(0.5)

                if self.stop:
                    return

            await sio.emit("update_status", data="Starting Game")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")

        # start menuing
        while True:
            try:
                if pyautogui.locateOnScreen("img/play_screen.png", confidence=0.9):
                    break
            except pyautogui.ImageNotFoundException:
                pass

            print("Waiting for play screen")
            await asyncio.sleep(0.5)

            try:
                if pyautogui.locateOnScreen("img/rejoin_prompt.png", confidence=0.9):
                    await asyncio.sleep(0.5)
                    keyboard.press_and_release("esc")
                    print("Declined rejoin prompt")
            except pyautogui.ImageNotFoundException:
                pass

            if self.stop:
                return

        # Wait for 3 seconds so the stupid popup has time to load
        await sio.emit("update_status", data="Waiting for the popup")
        await asyncio.sleep(3)

        # Check if the stupid popup is there, if it is, close it
        try:
            if pyautogui.locateOnScreen("img/stupid_popup_1.png", confidence=0.9):
                keyboard.press_and_release("esc")
                await asyncio.sleep(0.5)
                print("Closed popup")
        except pyautogui.ImageNotFoundException:
            pass

        try:
            if pyautogui.locateOnScreen("img/stupid_popup_2.png", confidence=0.9):
                keyboard.press_and_release("esc")
                await asyncio.sleep(0.5)
                print("Closed popup")
        except pyautogui.ImageNotFoundException:
            pass

        await sio.emit("update_status", data="Selecting gamemode")

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("right")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.6)

        # select ship
        print(self.ship)
        await sio.emit("update_status", data="Selecting ship")
        if self.ship == "Captaincy":
            keyboard.press_and_release("right")
            await asyncio.sleep(0.6)
            while True:
                try:
                    if pyautogui.locateOnScreen("img/captaincy_available.png", confidence=0.9):
                        break
                except pyautogui.ImageNotFoundException:
                    pass

                print("Waiting for captaincy to load")
                await asyncio.sleep(0.5)

                if self.stop:
                    return

            keyboard.press_and_release("enter")
            while True:
                try:
                    if pyautogui.locateOnScreen("img/ship_loaded.png", confidence=0.9):
                        break
                except pyautogui.ImageNotFoundException:
                    pass

                print("Waiting for captaincy ship to load")
                await asyncio.sleep(0.5)

                if self.stop:
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

        # get to set sail screen
        while True:
            try:
                if pyautogui.locateOnScreen("img/sail_screen.png", confidence=0.9):
                    break
            except pyautogui.ImageNotFoundException:
                pass

            print("Waiting for sail screen")
            await asyncio.sleep(0.5)

            if self.stop:
                return
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
        await asyncio.sleep(0.5)
        keyboard.press_and_release("alt+f4")

    async def stop_functions(self, sio):
        """
        Function that stops all running functions
        """
        await sio.emit("update_status", data="Stopping functions")
        self.stop = True
        await asyncio.sleep(2.5)
        self.stop = False
        await sio.emit("update_status", data="No longer stopping functions")
        await asyncio.sleep(2.5)
        await sio.emit("update_status", data="Pending...")

    async def auto_hold(self, sio):
        """
        Function that enables the auto holding feature
        """
        await sio.emit("update_status", data="(AH) Waiting for hold requests.")
        if self.holding:
            await sio.emit("update_status", data="(AH) Already holding.")
            await sio.emit("hold_request_ack", data="Already holding.")
            return

        self.holding = False

    async def hold_request(self, sio):
        """
        Function that tells this pc to start holding a ship
        """
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
        """
        Function that invites a person to the crew
        """
        await sio.emit("update_status", data=f"Inviting {person_to_invite}")
        self.activate_window("sea of thieves")
        await asyncio.sleep(0.2)
        #!! TODO: Disable AFK macro and wait for a bit at this point

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
        for i in range(9):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        keyboard.press_and_release("enter")
        print("Friends tab opened")
        await asyncio.sleep(1)
        print("searching for user")
        # 2 tabs to get to the friend search bar
        for i in range(2):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        await asyncio.sleep(1)
        # enter name of friend
        keyboard.write(person_to_invite)
        await asyncio.sleep(2.5)
        keyboard.press_and_release("enter")
        print("User found")
        await asyncio.sleep(6)
        print("Getting to invite button")
        # 5 tabs to get to user
        for i in range(5):
            keyboard.press_and_release("tab")
            await asyncio.sleep(0.5)
        # shift+f10 to emulate right click
        keyboard.press_and_release("shift+f10")
        await asyncio.sleep(1)
        # do two reverse tabs
        keyboard.press_and_release("shift+tab")
        await asyncio.sleep(0.5)
        keyboard.press_and_release("shift+tab")
        await asyncio.sleep(0.5)
        print("Inviting user")
        keyboard.press_and_release("enter")
        await asyncio.sleep(1)
        print("User invited")
        await sio.emit("update_status", data=f"Invited {person_to_invite}")

        #!! TODO: Re-enable AFK macro at this point
