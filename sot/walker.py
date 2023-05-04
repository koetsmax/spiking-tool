import keyboard
import asyncio
import vgamepad as vg

gamepad = vg.VX360Gamepad()


async def commute(outpost):
    # ancient spire
    if outpost == "Ancient Spire":
        keyboard.press("s")
        await asyncio.sleep(3)
        keyboard.release("s")
        await asyncio.sleep(1.5)

        keyboard.press("a")
        await asyncio.sleep(0.7)
        keyboard.release("a")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(-1, -1)
        gamepad.update()
        await asyncio.sleep(0.75)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press("w")
        keyboard.press("a")
        await asyncio.sleep(0.2)
        keyboard.release("w")
        keyboard.release("a")
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")

    elif outpost == "Galleons Grave":
        keyboard.press("d")
        await asyncio.sleep(5.05)
        keyboard.release("d")
        await asyncio.sleep(1.5)

        keyboard.press("w")
        await asyncio.sleep(2)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(0.75, -1)
        gamepad.update()
        await asyncio.sleep(0.75)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")

    # dagger tooth
    elif outpost == "Dagger Tooth":
        keyboard.press("d")
        await asyncio.sleep(9)
        keyboard.release("d")
        await asyncio.sleep(1.5)

        keyboard.press("s")
        await asyncio.sleep(11)
        keyboard.release("s")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(0.75, -0.2)
        gamepad.update()
        await asyncio.sleep(1.5)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press("w")
        keyboard.press("a")
        await asyncio.sleep(1)
        keyboard.release("w")
        keyboard.release("a")
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")

    # port merrick
    elif outpost == "Port Merrick":
        keyboard.press("a")
        await asyncio.sleep(7)
        keyboard.release("a")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(-1, 0)
        gamepad.update()
        await asyncio.sleep(0.9)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press("a")
        keyboard.press("s")
        await asyncio.sleep(0.8)
        keyboard.release("a")
        keyboard.release("s")
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")
        await asyncio.sleep(1.5)

        keyboard.press("w")
        await asyncio.sleep(3)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        # after ladder grab
        keyboard.press("w")
        await asyncio.sleep(0.3)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        keyboard.press("d")
        await asyncio.sleep(1.3)
        keyboard.release("d")
        await asyncio.sleep(1.5)

        keyboard.press("w")
        await asyncio.sleep(4)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        keyboard.press("a")
        await asyncio.sleep(3)
        keyboard.release("a")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(0.90, -0.45)
        gamepad.update()
        await asyncio.sleep(1)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press("w")
        await asyncio.sleep(1)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")

    # sanctuary
    elif outpost == "Sanctuary":
        keyboard.press("a")
        await asyncio.sleep(7.5)
        keyboard.release("a")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(-1, -0.2)
        gamepad.update()
        await asyncio.sleep(1.15)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")

    elif outpost == "Plunder":
        keyboard.press("a")
        await asyncio.sleep(0.2)
        keyboard.release("a")
        await asyncio.sleep(1.5)

        keyboard.press("s")
        await asyncio.sleep(3)
        keyboard.release("s")
        await asyncio.sleep(1.5)

        keyboard.press("d")
        await asyncio.sleep(1.75)
        keyboard.release("d")
        await asyncio.sleep(1.5)

        keyboard.press("w")
        await asyncio.sleep(0.6)
        keyboard.release("w")
        await asyncio.sleep(1.5)

        gamepad.right_joystick_float(-1, -1)
        gamepad.update()
        await asyncio.sleep(0.6)
        gamepad.reset()
        gamepad.update()
        await asyncio.sleep(1.5)

        keyboard.press_and_release("f")
