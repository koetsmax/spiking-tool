import asyncio
import queue
import threading
import traceback

import socketio

from events import EventManager


class ThreadedSocketClient:
    """Socket.IO client on a background thread for Qt and other non-async UIs."""

    def __init__(self, url, auth, *, autostart: bool = True):
        self._url = url
        self._auth = auth
        self.sio = socketio.AsyncClient()
        self.events = EventManager(asyncd=False)
        self.added_events = set()
        self.emit_queue = queue.Queue()
        self._thread: threading.Thread | None = None
        if autostart:
            self.start()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._thread_main,
            args=(self._url, self._auth),
            daemon=True,
        )
        self._thread.start()

    async def _connection_loop(self, url, auth):
        while True:
            try:
                await self.sio.connect(url, auth=auth)
                await self.sio.wait()
            except socketio.exceptions.ConnectionError:
                await asyncio.sleep(1)
            except Exception:
                traceback.print_exc()
                await asyncio.sleep(1)

    async def _emit_loop(self):
        while True:
            try:
                while event := self.emit_queue.get(block=False):
                    await self.sio.emit(event[0], event[1])
            except queue.Empty:
                pass
            except asyncio.CancelledError:
                break
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(0.1)

    def _thread_main(self, url, auth):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                asyncio.gather(
                    self._connection_loop(url, auth),
                    self._emit_loop(),
                )
            )
        finally:
            loop.close()

    def emit(self, name, data=None):
        self.emit_queue.put((name, data))

    def event(self):
        def decorator(func):
            event_name = func.__name__

            if event_name not in self.added_events:
                self.added_events.add(event_name)
                self.events.addEvent(event_name)
            self.events.events[event_name] += func
            self.sio.on(event_name)(self.events.events[event_name])
            return func

        return decorator
