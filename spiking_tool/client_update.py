"""Auto-update for the packaged spiking-tool client."""

from __future__ import annotations

import logging
import os
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

# Fallback when PyInstaller _MEIPASS bundle is not readable (shutil.copy/copymode fails).
_UPDATE_PS1 = """\
param (
    [string]$old_executable_path,
    [int]$process_id
)

Write-Output "Updating Spiking Tool client..."

$ErrorActionPreference = "Stop"

try {
    Start-Sleep -Seconds 2

    $process = Get-Process -Id $process_id -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $process_id -Force
        Start-Sleep -Seconds 1
    }

    $updated_executable_path = "$env:LOCALAPPDATA\\SpikingTool\\updater\\client.exe"

    if (-not (Test-Path $updated_executable_path)) {
        throw "Downloaded update not found at $updated_executable_path"
    }

    $backupPath = "$old_executable_path.old"
    if (Test-Path $backupPath) {
        Remove-Item -Path $backupPath -Force
    }
    Rename-Item -Path $old_executable_path -NewName (Split-Path -Leaf $backupPath)
    Move-Item -Path $updated_executable_path -Destination $old_executable_path
    Remove-Item -Path $backupPath -ErrorAction SilentlyContinue

    Start-Process -FilePath $old_executable_path

    Write-Output "Update completed successfully."
}
catch {
    Write-Host "An error occurred during update:" -ForegroundColor Red
    $_ | Format-List * -Force
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}
"""


def release_version(tag_name: str) -> str:
    """Normalize a GitHub release tag for version comparison."""
    return tag_name.lstrip("vV")


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def _updater_dir() -> str:
    return os.path.join(os.environ["LOCALAPPDATA"], "SpikingTool", "updater")


def _update_script_candidates() -> list[str]:
    paths: list[str] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        paths.append(os.path.join(sys._MEIPASS, "update.ps1"))
    paths.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "update.ps1"))
    return paths


def _update_script_source() -> str:
    for path in _update_script_candidates():
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read()
        except OSError as exc:
            logger.debug("Could not read update script from %s: %s", path, exc)
    return _UPDATE_PS1


def _prepare_updater_script(updater_dir: str) -> str:
    os.makedirs(updater_dir, exist_ok=True)
    script_destination = os.path.join(updater_dir, "update.ps1")
    with open(script_destination, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(_update_script_source())
    return script_destination


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
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

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
    os.makedirs(updater_dir, exist_ok=True)
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
