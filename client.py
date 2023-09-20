import asyncio
import ctypes
import sys
import traceback

import socketio
import tomlkit

import sot


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
            config_file[key] = input(f"Enter {key} of this client: ") if value == "prompt" else value

    with open("config.toml", "w", encoding="UTF=8") as f:
        f.write(tomlkit.dumps(config_file))

    return config_file


async def main():
    sio = socketio.AsyncClient()
    sotc = sot.ConnectionManager()
    sota = sot.AutomationManager()

    # Check if database is up-to-date

    config = get_config()

    @sio.event()
    async def region(data):
        sotc.region = sot.region_from_name(data)
        print(f"Region set to {sotc.region.city}")

    @sio.event()
    async def portspiking(data):
        sotc.portspike = data
        print(f"Portspiking set to {sotc.portspike}")

    @sio.event()
    async def safe_mode(data):
        await sota.set_safe_mode(data)

    @sio.event()
    async def client_ship(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.set_ship(sio, data["ship_type"])

    @sio.event()
    async def launch_game(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.launch_game(sio, leave=False)

    @sio.event()
    async def sail(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.sail(sio, sotc.portspike)

    @sio.event()
    async def reset(data):
        for client in data["client"]:
            if client == config_file["name"]:
                leave = True
                await sota.reset(sio, leave, sotc.portspike)

    @sio.event()
    async def kill_game(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.kill_game(sio)

    @sio.event()
    async def stop_functions(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.stop_functions(sio)

    async def on_join(ip, port):
        try:
            await sio.emit("join", {"ip": ip, "port": port})
        except:
            traceback.print_exc()

    sotc.events.join += on_join

    auth = {"name": config["name"], "type": "client"}

    while True:
        try:
            await sio.connect(config["url"], auth=auth)
            await sio.wait()
        except socketio.exceptions.ConnectionError:
            pass
        except:
            traceback.print_exc()


if __name__ == "__main__":
    if is_admin():
        try:
            asyncio.run(main())
        except:  # pylint: disable=bare-except
            traceback.print_exc()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
