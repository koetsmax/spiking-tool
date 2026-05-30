import asyncio

import keyboard

from .ui_automation import (
    SCREEN_POLL_SECONDS,
    GameScreenMatcher,
    ResolutionCheckResult,
)


class AutomationManager:
    def __init__(self):
        self.stop = False
        self.ship = "Brigantine"
        self.holding = False
        self.screen = GameScreenMatcher(should_stop=lambda: self.stop)
        self._check_resolution_after_launch = False
        self._resolution_metric_state: str | None = None
        self._session_load = None

    def set_session_load_tracker(self, tracker) -> None:
        self._session_load = tracker

    def activate_window(self):
        self.screen.activate_window()

    async def quit_game_gracefully(self) -> bool:
        """Request game shutdown via WM_CLOSE and wait for sotgame.exe to exit."""
        return await asyncio.to_thread(self.screen.request_close_game, 30.0)

    async def leave_session_via_menu(self) -> None:
        """Return to the title screen through the in-game menu without closing the game."""
        self.activate_window()
        await asyncio.sleep(0.2)
        keyboard.press_and_release("esc")
        await asyncio.sleep(1.2)
        for _ in range(7):
            keyboard.press_and_release("down")
            await asyncio.sleep(0.3)
        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        keyboard.press_and_release("enter")

    async def _emit_quit_game_status(self, sio, closed: bool) -> None:
        if closed:
            await sio.emit("update_status", data="Game closed")
        else:
            await sio.emit("update_status", data="Game still running after close request")

    def check_game_resolution(self):
        return self.screen.ensure_target_resolution()

    @staticmethod
    def resolution_metric_state(result: ResolutionCheckResult) -> str:
        if result.status in ("ok", "resized"):
            return "ok"
        if result.status == "no_window":
            return "unknown"
        return "bad"

    async def emit_resolution_metric(
        self,
        sio,
        result: ResolutionCheckResult | None = None,
        *,
        force: bool = False,
    ) -> None:
        if result is None:
            result = self.screen.check_target_resolution()
        state = self.resolution_metric_state(result)
        if not force and state == self._resolution_metric_state:
            return
        self._resolution_metric_state = state
        await sio.emit(
            "client_metric",
            data={
                "metric": "resolution",
                "state": state,
            },
        )

    async def _maybe_fix_and_report_resolution(self, sio) -> None:
        if self.screen.should_skip_resize():
            check = self.screen.check_target_resolution()
            await self.emit_resolution_metric(sio, check)
            return
        result = self.screen.ensure_target_resolution()
        await self.emit_resolution_metric(sio, result, force=True)

    async def report_game_resolution(self, sio) -> None:
        await asyncio.to_thread(self.screen.wait_until_ready_to_resize, 120.0)
        result = self.check_game_resolution()
        await self.emit_resolution_metric(sio, result, force=True)

    async def wait_for_screen(
        self,
        sio,
        image_path,
        message=None,
        *,
        fix_resolution: bool = False,
    ):
        if not fix_resolution:
            return await self.screen.wait_for_screen(image_path, message=message)

        polls = 0
        while True:
            if polls % 5 == 0:
                await self._maybe_fix_and_report_resolution(sio)
            if self.screen.screen_visible(image_path):
                await self._maybe_fix_and_report_resolution(sio)
                return True
            polls += 1
            if message:
                print(message)
            await asyncio.sleep(SCREEN_POLL_SECONDS)
            if self.stop:
                return False

    async def wait_for_play_screen(self, sio):
        async def on_promo_skipped():
            await sio.emit("update_status", data="Skipped promo video")

        return await self.screen.wait_for_play_screen(on_promo_skipped=on_promo_skipped)

    async def dismiss_popup_if_visible(self, image_path):
        await self.screen.dismiss_popup_if_visible(image_path)

    async def set_ship(self, sio, ship_type):
        self.ship = ship_type
        await sio.emit("update_status", data=f"Ship set to {self.ship}")

    async def launch_game(self, sio, leave):
        self._check_resolution_after_launch = True
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
        self.activate_window()
        await asyncio.sleep(0.2)

        if not await self.wait_for_screen(
            sio,
            "img/portspike_connected.png",
            "waiting for portspike client to connect",
        ):
            return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data="Awaiting rejoin prompt")
        if not await self.wait_for_screen(sio, "img/rejoin_prompt.png", "waiting for rejoin prompt"):
            return

        keyboard.press_and_release("enter")
        await asyncio.sleep(0.3)
        await sio.emit("update_status", data=f"Rejoining {port}")

    async def wait_until_session_loaded(self, sio, *, already_loaded_ok: bool = False) -> bool:
        if self._session_load is None:
            return True
        if not await self._session_load.wait_until_loaded(already_loaded_ok=already_loaded_ok):
            await sio.emit("update_status", data="Timed out waiting to load in")
            return False
        return True

    async def reset(self, sio, leave, portspiking):
        if portspiking:
            if self._session_load is not None:
                self._session_load.cancel()
            await sio.emit("update_status", data="Awaiting connection")
            self.activate_window()
            await asyncio.sleep(0.2)
            if not await self.wait_for_screen(
                sio,
                "img/portspike_connected.png",
                "waiting for portspike client to connect",
            ):
                return

            keyboard.press_and_release("enter")
            await asyncio.sleep(0.3)
            await sio.emit("update_status", data="Awaiting rejoin prompt")
            if not await self.wait_for_screen(sio, "img/rejoin_prompt.png", "waiting for rejoin prompt"):
                return

            keyboard.press_and_release("esc")
        elif leave:
            if self._session_load is not None:
                self._session_load.begin_reset_wait()
                await sio.emit("update_status", data=self._session_load.waiting_to_load_status())
            else:
                await sio.emit("update_status", data="Waiting to load")
            try:
                if not await self.wait_until_session_loaded(sio, already_loaded_ok=True):
                    return
            finally:
                if self._session_load is not None:
                    self._session_load.end_reset_wait()
            await sio.emit("update_status", data="Leaving Game")
            await self.leave_session_via_menu()

        if not portspiking:
            if self._check_resolution_after_launch:
                self._check_resolution_after_launch = False
                await self.report_game_resolution(sio)
            else:
                check = self.screen.check_target_resolution()
                if check.status not in ("ok", "no_window"):
                    result = self.screen.ensure_target_resolution()
                    await self.emit_resolution_metric(sio, result)

            if not await self.wait_for_screen(
                sio,
                "img/start_screen.png",
                "Waiting for start screen",
                fix_resolution=True,
            ):
                return

            await sio.emit("update_status", data="Starting Game")
            await asyncio.sleep(0.3)
            keyboard.press_and_release("enter")

        if not await self.wait_for_play_screen(sio):
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
                sio,
                "img/captaincy_available.png",
                "Waiting for captaincy to load",
            ):
                return

            keyboard.press_and_release("enter")
            if not await self.wait_for_screen(
                sio,
                "img/ship_loaded.png",
                "Waiting for captaincy ship to load",
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

        if not await self.wait_for_screen(sio, "img/sail_screen.png", "Waiting for sail screen"):
            return

        await sio.emit("update_status", data="Ready")
        print("waiting on set sail screen")

    async def kill_game(self, sio):
        await sio.emit("update_status", data="Killing Game")
        await self._emit_quit_game_status(sio, await self.quit_game_gracefully())

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
