import asyncio
import os
import shutil
import sys
import tarfile
import time
import traceback

import pyuac
import requests
import socketio
import sot
import tomlkit


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

    with open("config.toml", "w", encoding="UTF=8") as f:
        f.write(tomlkit.dumps(config_file))

    return config_file


async def main():
    print("checking for updates...")
    # check for updates
    with open("VERSION", "r") as f:
        version = f.read()
    request = requests.get("https://api.github.com/repos/koetsmax/spiking-tool/releases/latest", timeout=15)
    if request.status_code != 200:
        print("Failed to check for updates. Error code: ", request.status_code)
    else:
        request_dictionary = request.json()
        with open("version", "r", encoding="UTF-8") as versionfile:
            local_version = versionfile.read()
        online_version = request_dictionary["name"]
        if version.parse(local_version) < version.parse(online_version):
            url = f"https://github.com/koetsmax/spiking-tool/releases/download/{online_version}/Client.exe"  # pylint: disable=line-too-long
            download = requests.get(url, allow_redirects=True, timeout=30)
            # overwrite the old exe with the new one
            with open("TempClient.exe", "wb") as f:
                f.write(download.content)
            print("Client updated. Restarting...")
            # launch the powershelll script to replace the old exe with the new one
            os.system("powershell.exe -ExecutionPolicy Bypass -File update.ps1")
            sys.exit(0)

        else:
            print("Client up-to-date...")

    print("Starting Client...")
    print("Launching afk macro...")
    # start the exe
    try:
        os.startfile("afk\\anti-afk-v2.exe")
        print("afk macro launched...")
    except Exception as e:
        print("Failed to launch afk macro...", e)

    print("Checking database...")
    # Check if database is up-to-date
    SpikeToolTemp = os.path.join(os.environ["LOCALAPPDATA"], "SpikingTool")
    if not os.path.exists(SpikeToolTemp):
        os.makedirs(SpikeToolTemp)

    mmdbFolder = os.path.join(SpikeToolTemp, "mmdb")
    if not os.path.exists(mmdbFolder):
        os.makedirs(mmdbFolder)

    files = os.listdir(mmdbFolder)

    timestamp = 0
    if len(files) > 0:
        if files[0].endswith(".mmdb"):
            fName = files[0].split(".")[0]
            try:
                timestamp = int(fName)
            except:
                pass

    if timestamp < (int(time.time()) - 86400):
        print("Database out of date...")
        print("Clearing database folder...")
        for file in os.listdir(mmdbFolder):
            try:
                os.remove(os.path.join(mmdbFolder, file))
            except:
                pass

        print("Downloading new IP database...")
        fname = str(int(time.time())) + ".mmdb"
        tarName = "mmdb.tar.gz"
        defaultName = "GeoLite2-City.mmdb"
        with open(os.path.join(mmdbFolder, tarName), "wb") as f:
            with requests.get("https://ipdb.ashen.info") as r:
                f.write(r.content)
        with tarfile.open(os.path.join(mmdbFolder, tarName)) as tar:
            tar.extractall(mmdbFolder)
        os.remove(os.path.join(mmdbFolder, tarName))
        tempFolder = os.path.join(mmdbFolder, os.listdir(mmdbFolder)[0])
        with open(os.path.join(tempFolder, defaultName), "rb") as f:
            with open(os.path.join(mmdbFolder, fname), "wb") as on:
                on.write(f.read())
        shutil.rmtree(tempFolder)
        print("Database updated...")
    else:
        print("Database already up-to-date...")

    sio = socketio.AsyncClient()
    sotc = sot.ConnectionManager()
    sota = sot.AutomationManager()

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
    async def rejoin_session(data):
        for client in data["client"]:
            if client == config_file["name"]:
                await sota.rejoin_session(sio, sotc.portspike, port=prev_port if prev_port else None)

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
            global prev_port
            prev_port = int(port)
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
    if pyuac.isUserAdmin():
        try:
            asyncio.run(main())
        except:  # pylint: disable=bare-except
            traceback.print_exc()
    else:
        pyuac.runAsAdmin(wait=False)
        sys.exit(0)
