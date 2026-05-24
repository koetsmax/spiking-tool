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


def release_version(tag_name: str) -> str:
    """Normalize a GitHub release tag for version comparison."""
    return tag_name.lstrip("vV")


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


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
        if str(asset.get("name", "")).lower() == "client.exe":
            return asset["browser_download_url"]

    tag = release.get("tag_name")
    if tag:
        return (
            f"https://github.com/koetsmax/spiking-tool/releases/download/"
            f"{tag}/client.exe"
        )
    return None


def download_file(url: str, dest: str, *, timeout: int = 120) -> bool:
    try:
        with requests.get(
            url,
            stream=True,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": GITHUB_USER_AGENT},
        ) as response:
            response.raise_for_status()
            total = 0
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        handle.write(chunk)
                        total += len(chunk)

            if total < MIN_CLIENT_EXE_BYTES:
                logger.error("Downloaded update looks too small (%d bytes)", total)
                os.remove(dest)
                return False
            return True
    except (OSError, requests.RequestException) as exc:
        logger.warning("Failed to download update: %s", exc)
        if os.path.isfile(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        return False


def _ps_single_quote(value: str) -> str:
    return value.replace("'", "''")


def _write_apply_update_script(
    script_path: str,
    *,
    current_exe: str,
    new_exe: str,
    pid: int,
) -> None:
    script = f"""$ErrorActionPreference = "Stop"
$currentExe = '{_ps_single_quote(current_exe)}'
$newExe = '{_ps_single_quote(new_exe)}'
$pidToWait = {pid}

for ($i = 0; $i -lt 120; $i++) {{
    if (-not (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue)) {{
        break
    }}
    Start-Sleep -Milliseconds 500
}}
Start-Sleep -Seconds 1

if (Test-Path $currentExe) {{
    Remove-Item -Path $currentExe -Force
}}
Move-Item -Path $newExe -Destination $currentExe -Force
Start-Process -FilePath $currentExe
"""
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write(script)


def _launch_update_script(script_path: str, app_dir: str) -> None:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            script_path,
        ],
        cwd=app_dir,
        close_fds=True,
        creationflags=creationflags,
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

    app_dir = _app_dir()
    current_exe = os.path.abspath(sys.executable)
    new_exe = os.path.join(app_dir, "Client.update.exe")
    script_path = os.path.join(app_dir, "apply_update.ps1")

    if os.path.isfile(new_exe):
        try:
            os.remove(new_exe)
        except OSError as exc:
            logger.warning("Could not remove stale update file: %s", exc)
            return False

    logger.info("Updating client %s -> %s", current_version, online_version)
    if not download_file(download_url, new_exe):
        return False

    try:
        _write_apply_update_script(
            script_path,
            current_exe=current_exe,
            new_exe=new_exe,
            pid=os.getpid(),
        )
        _launch_update_script(script_path, app_dir)
    except OSError as exc:
        logger.error("Failed to schedule update restart: %s", exc)
        return False

    logger.info("Update downloaded; restarting...")
    return True
