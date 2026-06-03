"""Unified client diagnostics: local file + controller remote log."""

from __future__ import annotations

import logging
import os
import queue
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import socketio

_DIAGNOSTIC_LOGGER_NAME = "spiking_tool.client"
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_CLIENT_LOG_FILENAME = "spiking-tool-client.log"

_diagnostic_logger = logging.getLogger(_DIAGNOSTIC_LOGGER_NAME)


def client_logs_dir() -> str:
    if getattr(sys, "frozen", False):
        logs_dir = os.path.join(os.path.expanduser("~"), "Desktop", "logs")
    else:
        logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def client_log(message: str, level: str = "INFO") -> None:
    """Write to the local log file and queue for the controller when connected."""
    text = message.rstrip()
    if not text:
        return
    log_level = getattr(logging, level, logging.INFO)
    _diagnostic_logger.log(log_level, text)


class _RemoteLogBridge:
    def __init__(self, max_queue: int = 5000) -> None:
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=max_queue)
        self._sio: Optional["socketio.AsyncClient"] = None
        self._client_name = ""
        self._pump_running = False

    def enqueue(self, message: str, level: str) -> None:
        try:
            self._queue.put_nowait((message, level))
        except queue.Full:
            pass

    def attach(self, sio: "socketio.AsyncClient", client_name: str) -> None:
        self._sio = sio
        self._client_name = client_name

    def start_pump_task(self) -> None:
        import asyncio

        if self._pump_running:
            return
        self._pump_running = True
        asyncio.create_task(self.pump())

    async def pump(self) -> None:
        import asyncio

        while True:
            if self._sio is not None and self._client_name:
                batch: list[tuple[str, str]] = []
                try:
                    while len(batch) < 40:
                        batch.append(self._queue.get_nowait())
                except queue.Empty:
                    pass
                for message, level in batch:
                    try:
                        await self._sio.emit(
                            "client_log",
                            data={
                                "client": self._client_name,
                                "message": message,
                                "level": level,
                            },
                        )
                    except Exception:
                        pass
            await asyncio.sleep(0.05)


_bridge = _RemoteLogBridge()


def attach_client_log_transport(sio: "socketio.AsyncClient", client_name: str) -> None:
    _bridge.attach(sio, client_name)


def start_client_log_pump() -> None:
    _bridge.start_pump_task()


class _RemoteLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _bridge.enqueue(self.format(record), record.levelname)
        except Exception:
            self.handleError(record)


class _StreamToLogger:
    def __init__(self, level: int = logging.INFO) -> None:
        self._level = level

    def write(self, text: str) -> None:
        if not text or text.isspace():
            return
        for line in text.rstrip().splitlines():
            client_log(line, logging.getLevelName(self._level))

    def flush(self) -> None:
        pass


def _add_file_handler(root: logging.Logger, level: int) -> str:
    log_path = os.path.join(client_logs_dir(), _CLIENT_LOG_FILENAME)
    abs_log_path = os.path.abspath(log_path)
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            if os.path.abspath(handler.baseFilename) == abs_log_path:
                return log_path
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(file_handler)
    return log_path


def _add_remote_handler(root: logging.Logger) -> None:
    if any(isinstance(handler, _RemoteLogHandler) for handler in root.handlers):
        return
    handler = _RemoteLogHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)


def install_client_logging(level: int = logging.INFO, *, console_output: bool = False) -> str:
    """
    Configure client logging: always append to a local file; forward to the
    controller when the socket transport is attached.
    """
    root = logging.getLogger()
    root.setLevel(level)
    log_path = _add_file_handler(root, level)
    _add_remote_handler(root)
    if console_output:
        if not any(
            isinstance(handler, logging.StreamHandler) and not isinstance(handler, _RemoteLogHandler)
            for handler in root.handlers
        ):
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
            root.addHandler(stream_handler)
    else:
        sys.stdout = _StreamToLogger(logging.INFO)  # type: ignore[assignment]
        sys.stderr = _StreamToLogger(logging.ERROR)  # type: ignore[assignment]
    return log_path
