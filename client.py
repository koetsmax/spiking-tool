import asyncio
import ctypes
import sys
import traceback

import socketio
import tomlkit

import sot

ship_type = "Brigantine"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:  # pylint: disable=bare-except
        return False


config_defaults = {
    "name": "prompt",
    "url": "http://spiker.famkoets.nl",
}


def get_config():
    # read or create config.toml if it doesn't exist
    try:
        global config_file
        with open("config.toml", "r", encoding="UTF=8") as f:
            config_file = tomlkit.parse(f.read())

    except FileNotFoundError:
        config_file = tomlkit.document()
        config_file["name"] = input("Enter name of this client: ")
        config_file["url"] = "http://spiker.famkoets.nl"

    for key, value in config_defaults.items():
        try:
            config_file[key]
        except tomlkit.exceptions.NonExistentKey:
            config_file[key] = (
                input(f"Enter {key} of this client: ") if value == "prompt" else value
            )

    with open("config.toml", "w", encoding="UTF=8") as f:
        f.write(tomlkit.dumps(config_file))

    return config_file


async def main():
    sio = socketio.AsyncClient()
    sotc = sot.ConnectionManager()
    sota = sot.AutomationManager()

    config = get_config()

    @sio.event()
    async def connect():
        print("Connected to server")

    @sio.event()
    async def region(data):
        sotc.region = sot.Region.fromName(data)
        print(f"Region set to {sotc.region.name}")

    @sio.event()
    async def portspiking(data):
        sotc.portspike = data
        print(f"Portspiking set to {sotc.portspike}")

    @sio.event()
    async def client_ship(data):
        global ship_type
        ship_type = data

    @sio.event()
    async def launch_game(data):
        if config_file["name"] in data:
            await sota.launch_game(sio, ship_type, leave=False)

    @sio.event()
    async def sail(data):
        if config_file["name"] in data:
            await sota.sail(sio)

    @sio.event()
    async def reset(data):
        if config_file["name"] in data:
            leave = True
            await sota.reset(sio, ship_type, leave, sotc.portspike)

    @sio.event()
    async def kill_game(data):
        if config_file["name"] in data:
            await sota.kill_game(sio)

    async def on_join(ip, port):
        try:
            if sio.connected:
                await sio.emit("join", {"ip": ip, "port": port})
                print(
                    f"Join in {sotc.getServerInfo(ip)} detected and emitted: : {ip}:{port}"
                )
            else:
                print(f"Join detected in {sotc.getServerInfo(ip)}: {ip}:{port}")
        except:  # pylint: disable=bare-except
            traceback.print_exc()

    sotc.events.join += on_join

    auth = {"name": config["name"], "type": "client"}

    while True:
        try:
            await sio.connect(config["url"], auth=auth)
            await sio.wait()
        except socketio.exceptions.ConnectionError:
            pass
        except:  # pylint: disable=bare-except
            traceback.print_exc()
            input()


if __name__ == "__main__":
    if is_admin():
        try:
            asyncio.run(main())
        except:  # pylint: disable=bare-except
            traceback.print_exc()
            input()
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
