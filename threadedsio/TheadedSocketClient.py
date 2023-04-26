import threading
import socketio
import queue
import asyncio
import traceback
from events import EventManager


class ThreadedSocketClient():
    def __init__(self, url, auth):
        self.sio = socketio.AsyncClient()
        self.events = EventManager(asyncd=False)
        self.added_events = set()
        self.emitQueue = queue.Queue()
        self.thread = threading.Thread(
            target=self.thread_func,
            args=[url, auth],
            daemon=True
        )
        self.thread.start()

    async def socketio_thread(self, url, auth):
        await self.sio.connect(url, auth=auth)
        await self.sio.wait()

    def emit(self, name, data=None):
        self.emitQueue.put((name, data))

    def thread_func(self, url, auth):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task1 = loop.create_task(self.socketio_thread(url, auth))
        task2 = loop.create_task(self._emitTaskMethod())
        loop.run_until_complete(task1)
        loop.run_until_complete(task2)
    # task that checks eventQueue and triggers any events then sleeps

    async def _emitTaskMethod(self):
        while True:
            try:
                while event := self.emitQueue.get(block=False):
                    print(event)
                    await self.sio.emit(event[0], event[1])
            except queue.Empty:
                pass
            except asyncio.exceptions.CancelledError:
                print("test")
                break
            except:
                traceback.print_exc()
            await asyncio.sleep(0.1)

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
