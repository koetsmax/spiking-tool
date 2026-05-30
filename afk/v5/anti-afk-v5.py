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
            version = random.randint(1, 18)
            # create a list of version that correlate to keyboard keys
            version_table = {
                1: "w",
                2: "a",
                3: "s",
                4: "d",
                5: "1",
                6: "2",
                7: "b",
                8: "6",
                9: "7",
                10: "8",
                11: "9",
                12: "0",
                13: "ctrl",
                14: "x",
                15: "v",
                16: "i",
                17: "l",
                18: "k",
            }
            key_to_press = version_table[version]
            print(f"Chose {key_to_press} for {int(duration)} miliseconds")

            press_key(key_to_press, duration)
            if key_to_press == "ctrl":
                press_key(key_to_press, (1 * random.uniform(0.25, 1)))

            # Check if it has been 45 minutes since the afk macro started
            if time.time() - current_time >= 45 * 60:
                current_time = time.time()
                # reconnect and restart the afk macro
                print("Starting disconnect")
                sotc.force_disconnect = True
                time.sleep(45)
                print("Stopping disconnect")
                sotc.force_disconnect = False
                time.sleep(30)
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
                print(f"Time remaining before disconnect: {int(45 * 60 - (time.time() - current_time))} seconds")

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
