"""Auto-update for the packaged spiking-tool client."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

import requests
from packaging import version

logger = logging.getLogger(__name__)

GITHUB_RELEASES_LATEST = "https://api.github.com/repos/koetsmax/spiking-tool/releases/latest"
GITHUB_USER_AGENT = "spiking-tool-client"
MIN_CLIENT_EXE_BYTES = 5_000_000
DOWNLOAD_ATTEMPTS = 3
UPDATED_EXE_NAME = "client.exe"


def release_version(tag_name: str) -> str:
    """Normalize a GitHub release tag for version comparison."""
    return tag_name.lstrip("vV")


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def _updater_dir() -> str:
    return os.path.join(os.environ["LOCALAPPDATA"], "SpikingTool", "updater")


def _bundled_update_script() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "update.ps1")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "update.ps1")


def _request_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": GITHUB_USER_AGENT,
    }


def fetch_latest_release() -> dict | None:
    try:
        response = requests.get(
            GITHUB_RELEASES_LATEST,
            headers=_request_headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning("Failed to check for updates: %s", exc)
        return None


def release_download_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if str(asset.get("name", "")).lower() == UPDATED_EXE_NAME:
            return asset["browser_download_url"]

    tag = release.get("tag_name")
    if tag:
        return (
            f"https://github.com/koetsmax/spiking-tool/releases/download/"
            f"{tag}/{UPDATED_EXE_NAME}"
        )
    return None


def download_file(url: str, dest: str, *, timeout: int = 120) -> bool:
    for attempt in range(DOWNLOAD_ATTEMPTS):
        try:
            logger.info("Downloading update (attempt %d/%d)...", attempt + 1, DOWNLOAD_ATTEMPTS)
            total = 0
            with requests.get(
                url,
                stream=True,
                allow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": GITHUB_USER_AGENT},
            ) as response:
                response.raise_for_status()
                with open(dest, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)
                            total += len(chunk)

            if total < MIN_CLIENT_EXE_BYTES:
                logger.error("Downloaded update looks too small (%d bytes)", total)
                os.remove(dest)
                continue
            return True
        except (OSError, requests.RequestException) as exc:
            logger.warning("Failed to download update: %s", exc)
            if os.path.isfile(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
    return False


def _prepare_updater_script(updater_dir: str) -> str:
    os.makedirs(updater_dir, exist_ok=True)
    bundled_script = _bundled_update_script()
    script_destination = os.path.join(updater_dir, "update.ps1")
    shutil.copy(bundled_script, script_destination)
    return script_destination


def _launch_update_script(script_path: str, current_exe: str) -> None:
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            "-old_executable_path",
            current_exe,
            "-process_id",
            str(os.getpid()),
        ],
        env=env,
    )


def maybe_update_client(current_version: str) -> bool:
    """
    Download and schedule an update when a newer release exists.

    Returns True when the current process should exit so the updater can run.
    """
    if not getattr(sys, "frozen", False):
        logger.debug("Skipping auto-update (not a packaged client)")
        return False

    release = fetch_latest_release()
    if not release:
        return False

    tag = release.get("tag_name")
    if not tag:
        logger.warning("Latest GitHub release has no tag_name")
        return False

    online_version = release_version(tag)
    try:
        if version.parse(current_version) >= version.parse(online_version):
            logger.info("Client up to date (%s)", current_version)
            return False
    except version.InvalidVersion as exc:
        logger.warning(
            "Could not compare versions %r and %r: %s",
            current_version,
            online_version,
            exc,
        )
        return False

    download_url = release_download_url(release)
    if not download_url:
        logger.warning("No client.exe asset found in release %s", tag)
        return False

    updater_dir = _updater_dir()
    updated_exe = os.path.join(updater_dir, UPDATED_EXE_NAME)
    if os.path.isfile(updated_exe):
        try:
            os.remove(updated_exe)
        except OSError as exc:
            logger.warning("Could not remove stale update file: %s", exc)
            return False

    logger.info("Updating client %s -> %s", current_version, online_version)
    if not download_file(download_url, updated_exe):
        return False

    try:
        script_path = _prepare_updater_script(updater_dir)
        _launch_update_script(script_path, os.path.abspath(sys.executable))
    except OSError as exc:
        logger.error("Failed to schedule update restart: %s", exc)
        return False

    logger.info("Update downloaded; restarting...")
    return True
