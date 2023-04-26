import asyncio
import queue
import threading
import traceback


class EventManager:
    class Event:
        def __init__(self, name, manager):
            self.name = name
            self.callbacks = []
            self.manager = manager
            self.event_tasks = set()

        # add events with + operator
        def __iadd__(self, callback):
            self.callbacks.append(callback)
            return self

        # remove events with - operator
        def __isub__(self, callback):
            self.callbacks.remove(callback)
            return self

        def __call__(self, *args, **kwds):
            # add event to manager eventQueue
            self.manager._triggerEvent(self.name, *args, **kwds)

        # call event with () operator
        def trigger(self, *args, **kwargs):
            for callback in self.callbacks:
                if self.manager.asyncd and asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(*args, **kwargs))
                    self.event_tasks.add(task)
                    task.add_done_callback(self.event_tasks.discard)
                else:
                    callback(*args, **kwargs)

    def __init__(self, asyncd=True, events=None):
        try:
            self.events = {}
            if events:
                for event in events:
                    self.addEvent(event)
            self.eventQueue = queue.Queue()
            self.asyncd = asyncd
            if self.asyncd:
                self._eventTask = asyncio.create_task(self._eventTaskMethod())
        except:
            traceback.print_exc()

    # task that checks eventQueue and triggers any events then sleeps
    async def _eventTaskMethod(self):
        while True:
            try:
                while event := self.eventQueue.get(block=False):
                    print(event)
                    self.events[event[0]].trigger(*event[1][0], **event[1][1])
            except queue.Empty:
                pass
            except:
                traceback.print_exc()
            await asyncio.sleep(0.1)

    def processEvents(self):
        try:
            while event := self.eventQueue.get(block=False):
                print(event)
                self.events[event[0]].trigger(*event[1][0], **event[1][1])
        except queue.Empty:
            pass
        except:
            traceback.print_exc()

    # add event to eventManager as attribute
    def addEvent(self, name):
        newEvent = self.Event(name, self)
        self.events[name] = newEvent
        setattr(self, name, newEvent)

    def _triggerEvent(self, name, *args, **kwargs):
        self.eventQueue.put((name, (args, kwargs)))
