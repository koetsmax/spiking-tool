"""Forward client logs to the spiking server for the controller logging tab."""

from __future__ import annotations

import logging
import queue
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import socketio


class RemoteLogBridge:
    def __init__(self, max_queue: int = 5000) -> None:
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=max_queue)
        self._sio: Optional["socketio.AsyncClient"] = None
        self._client_name = ""
        self._pump_running = False

    def enqueue(self, message: str, level: str = "INFO") -> None:
        text = message.rstrip()
        if not text:
            return
        try:
            self._queue.put_nowait((text, level))
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


remote_log_bridge = RemoteLogBridge()


class RemoteLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            remote_log_bridge.enqueue(self.format(record), record.levelname)
        except Exception:
            self.handleError(record)


class _StreamToLogger:
    def __init__(self, level: int = logging.INFO) -> None:
        self._level = level

    def write(self, text: str) -> None:
        if not text or text.isspace():
            return
        for line in text.rstrip().splitlines():
            remote_log_bridge.enqueue(line, logging.getLevelName(self._level))

    def flush(self) -> None:
        pass


def install_client_remote_logging(level: int = logging.INFO, *, console_output: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(handler, RemoteLogHandler) for handler in root.handlers):
        handler = RemoteLogHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    if console_output:
        if not any(
            isinstance(handler, logging.StreamHandler) and not isinstance(handler, RemoteLogHandler)
            for handler in root.handlers
        ):
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            root.addHandler(stream_handler)
    else:
        sys.stdout = _StreamToLogger(logging.INFO)  # type: ignore[assignment]
        sys.stderr = _StreamToLogger(logging.ERROR)  # type: ignore[assignment]
