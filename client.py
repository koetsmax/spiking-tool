import asyncio
import os
import shutil
import subprocess
import sys
import tarfile
import time
import traceback

import pyuac
import requests
import socketio
import tomlkit
from packaging import version

import logging

import sot
from client_handlers import ClientState, register_client_handlers
from spiking_tool.remote_log import install_client_remote_logging
from spiking_tool.win_console import hide_console_window

VERSION = "2.4.0"
logger = logging.getLogger(__name__)


def get_config():
    try:
        global config_file
        with open("config.toml", "r", encoding="UTF=8") as f:
            config_file = tomlkit.parse(f.read())

    except FileNotFoundError:
        config_file = tomlkit.document()
        config_file["name"] = input("Enter name of this client: ")
        config_file["url"] = "http://ashen.spiker.famkoets.nl"

    with open("config.toml", "w", encoding="UTF=8") as f:
        f.write(tomlkit.dumps(config_file))

    return config_file


def _show_console() -> bool:
    return os.environ.get("SPIKING_TOOL_SHOW_CONSOLE", "").lower() in ("1", "true", "yes")


async def main():
    install_client_remote_logging()
    if not _show_console():
        hide_console_window()

    logger.info("Checking for updates...")
    request = requests.get(
        "https://api.github.com/repos/koetsmax/spiking-tool/releases/latest",
        timeout=15,
    )
    if request.status_code != 200:
        logger.warning("Failed to check for updates. Error code: %s", request.status_code)
    else:
        request_dictionary = request.json()
        online_version = request_dictionary["name"]
        if version.parse(VERSION) < version.parse(online_version):
            url = (
                f"https://github.com/koetsmax/spiking-tool/releases/download/"
                f"{online_version}/Client.exe"
            )
            download = requests.get(url, allow_redirects=True, timeout=30)
            with open("TempClient.exe", "wb") as f:
                f.write(download.content)
            logger.info("Client updated. Restarting...")
            subprocess.Popen(["powershell.exe", "-File", "update.ps1"], shell=True)
            sys.exit(0)
        logger.info("Client up to date")

    logger.info("Starting client...")
    logger.info("Launching afk macro...")
    try:
        os.startfile("anti-afk-v2.exe")
        logger.info("AFK macro launched")
    except OSError as e:
        logger.warning("Failed to launch afk macro: %s", e)

    logger.info("Checking database...")
    spike_tool_temp = os.path.join(os.environ["LOCALAPPDATA"], "SpikingTool")
    os.makedirs(spike_tool_temp, exist_ok=True)

    mmdb_folder = os.path.join(spike_tool_temp, "mmdb")
    os.makedirs(mmdb_folder, exist_ok=True)

    files = os.listdir(mmdb_folder)
    timestamp = 0
    if files and files[0].endswith(".mmdb"):
        try:
            timestamp = int(files[0].split(".")[0])
        except (ValueError, TypeError):
            pass

    if timestamp < (int(time.time()) - 86400):
        logger.info("Database out of date")
        for file in os.listdir(mmdb_folder):
            try:
                os.remove(os.path.join(mmdb_folder, file))
            except OSError:
                pass

        logger.info("Downloading new IP database...")
        fname = str(int(time.time())) + ".mmdb"
        tar_name = "mmdb.tar.gz"
        default_name = "GeoLite2-City.mmdb"
        with open(os.path.join(mmdb_folder, tar_name), "wb") as f:
            with requests.get("https://ipdb.ashen.info", timeout=60) as r:
                f.write(r.content)
        with tarfile.open(os.path.join(mmdb_folder, tar_name)) as tar:
            tar.extractall(mmdb_folder)
        os.remove(os.path.join(mmdb_folder, tar_name))
        temp_folder = os.path.join(mmdb_folder, os.listdir(mmdb_folder)[0])
        with open(os.path.join(temp_folder, default_name), "rb") as f:
            with open(os.path.join(mmdb_folder, fname), "wb") as out:
                out.write(f.read())
        shutil.rmtree(temp_folder)
        logger.info("Database updated")
    else:
        logger.info("Database already up to date")

    sio = socketio.AsyncClient()
    connection = sot.ConnectionManager()
    automation = sot.AutomationManager()
    config = get_config()
    register_client_handlers(sio, config["name"], connection, automation, ClientState())

    auth = {"name": config["name"], "type": "client"}

    while True:
        try:
            await sio.connect(config["url"], auth=auth)
            await sio.wait()
        except socketio.exceptions.ConnectionError:
            pass
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    if pyuac.isUserAdmin():
        try:
            asyncio.run(main())
        except Exception:
            traceback.print_exc()
    else:
        pyuac.runAsAdmin(wait=False)
        sys.exit(0)
