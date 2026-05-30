import time
import keyboard
import random
import sot
import pyuac
import asyncio
import sys
import traceback

anti_afk = False


def press_key(key, duration):
    # press the key
    keyboard.press(key)
    time.sleep(duration / 1000)
    keyboard.release(key)


# create the anti afk toggle
def on_f12_press():
    global anti_afk
    anti_afk = not anti_afk
    print("Anti-AFK is now:", anti_afk)


keyboard.add_hotkey("f12", on_f12_press)


async def main():
    sotc = sot.DumbConnectionManager()
    current_time = time.time()
    while True:
        time.sleep(0.1)

        while anti_afk:
            # print("key_press")
            # create a random multiplier in range of .25 to 1
            multiplier = random.uniform(0.25, 1)
            duration = multiplier * 500
            key_to_press = "space"
            print(f"Chose {key_to_press} for {int(duration)} miliseconds")

            press_key(key_to_press, duration)

            # Check if it has been 1 minute since the afk macro started
            if time.time() - current_time >= 1 * 60:
                current_time = time.time()
                # reconnect and restart the afk macro
                print("Starting disconnect")
                sotc.force_disconnect = True
                time.sleep(45)
                print("Stopping disconnect")
                sotc.force_disconnect = False
                # wait 8 minutes before accepting the hazelnut error
                time.sleep(8 * 60)
                print("Accepting Hazelnut error")
                keyboard.press("enter")
                time.sleep((1 * random.uniform(0.25, 1)))
                keyboard.release("enter")
                time.sleep(20)
                print("Accepting Rejoin prompt")
                keyboard.press("enter")
                time.sleep((1 * random.uniform(0.25, 1)))
                keyboard.release("enter")
                time.sleep(45)

            else:
                # show time remaining
                print(f"Time remaining before disconnect: {int(1 * 60 - (time.time() - current_time))} seconds")

            multiplier = random.uniform(0.25, 1)
            duration = multiplier * 120
            print(f"Sleeping for {int(duration)} seconds")
            time.sleep(duration)


if __name__ == "__main__":
    if pyuac.isUserAdmin():
        try:
            asyncio.run(main())
        except Exception:
            traceback.print_exc()
    else:
        pyuac.runAsAdmin(wait=False)
        sys.exit(0)
