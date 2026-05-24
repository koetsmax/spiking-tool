"""Local file logging for the spiking-tool client."""

from __future__ import annotations

import logging
import os
import sys


def client_logs_dir() -> str:
    if getattr(sys, "frozen", False):
        logs_dir = os.path.join(os.path.expanduser("~"), "Desktop", "logs")
    else:
        logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def install_client_local_file_logging(level: int = logging.INFO) -> str:
    """Append client logs to a local file in the logs directory."""
    log_path = os.path.join(client_logs_dir(), "spiking-tool-client.log")
    root = logging.getLogger()
    abs_log_path = os.path.abspath(log_path)

    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            if os.path.abspath(handler.baseFilename) == abs_log_path:
                return log_path

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(file_handler)
    return log_path
