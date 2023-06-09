import pydivert
import asyncio
import traceback
import queue
from time import sleep, monotonic_ns
import threading
from events import EventManager
from .Region import region_from_name
from geolite2 import geolite2

voice_bytes = b"\x17\xfe\xfd\x00\x01\x00\x00"
join_bytes = b"\x00\xde\x51\xea\x05"


class ConnectionManager:
    class DelayedPacket:
        def __init__(self, packet, delay):
            self.packet = packet
            self.delay = delay

    def __init__(self, region="US East - NY/NJ"):
        try:
            self.region = region_from_name(region)
            print("Region:", self.region, "City:", self.region.city, "Country:", self.region.country, "Shorthand:", self.region.shorthand)
            self.packetQueue = queue.Queue()
            self.events = EventManager(events=["join"])
            self.disconnect = False
            self.lastConnected = {"server": None, "time": 0}
            self.packetTasks = set()

            self.portspike = False

            self.send_lock = threading.Lock()
            self.reader = geolite2.reader()
            self.reader_lock = threading.Lock()

            self._delayedSendTask = asyncio.create_task(self._delayedPackageSender())
            self.divertThread = threading.Thread(target=self._divert_SoT)

            self.divertThread.start()
        except:
            traceback.print_exc()

    async def _delayedPackageSender(self):
        while True:
            try:
                while packet := self.packetQueue.get(block=False):
                    await asyncio.sleep(packet.delay)
                    task = asyncio.create_task(asyncio.to_thread(self._threadSafeSend, packet.packet))
                    self.packetTasks.add(task)
                    task.add_done_callback(self.packetTasks.discard)
            except queue.Empty:
                pass
            except:
                traceback.print_exc()
            await asyncio.sleep(0.1)

    def _threadSafeSend(self, packet):
        with self.send_lock:
            self._winDivert.send(packet)

    def _delayedSend(self, packet, delay):
        self.packetQueue.put(self.DelayedPacket(packet, delay))

    def _divert_SoT(self):
        self._winDivert = pydivert.WinDivert("udp.DstPort == 3075 or (udp.DstPort >= 30000 and udp.DstPort < 31000)")
        self._winDivert.open()
        self.timeout = 0
        print("Listening for SoT packets...")

        while True:
            try:
                packet = self._winDivert.recv()
                try:
                    if self.disconnect:
                        # wait for 30 seconds after last timeout
                        if monotonic_ns() - self.timeout > 5 * 1000000000:
                            self.disconnect = False
                        else:
                            print("tried:", monotonic_ns() / 1000000000, packet.direction)
                            continue
                    if packet.dst_port == 3075:
                        if packet.is_outbound:
                            with self.reader_lock:
                                match = self.reader.get(packet.dst_addr)
                            try:
                                locationName = match["city"]["names"]["en"]  # type: ignore
                            except Exception:
                                try:
                                    locationName = match["country"]["names"]["en"]  # type: ignore
                                except Exception:
                                    locationName = "Unknown"
                            print(f"Connecting to {locationName} ({packet.dst_addr})")
                            if not "city" in match or match["city"]["names"]["en"] != self.region.city:
                                print(f"Not preferred: {locationName} | {packet.dst_addr}")
                                self._delayedSend(packet, 0.5)
                                continue
                            else:
                                print(f"prefered: {match['city']['names']['en']} | {packet.dst_addr}")
                    else:
                        if packet.is_outbound and len(packet.payload) == 51 and packet.payload[0:4] == join_bytes[0:4]:
                            self.events.join(packet.dst_addr, packet.dst_port)
                            if self.portspike:
                                self.disconnect = True
                                self.timeout = monotonic_ns()

                except:
                    traceback.print_exc()
                with self.send_lock:
                    self._winDivert.send(packet)  # re-inject the packet into the network stack
            except Exception as e:
                traceback.print_exc()

    def getServerInfo(self, ip):
        try:
            with self.reader_lock:
                match = self.reader.get(ip)
            if "city" in match:
                return match["city"]["names"]["en"]
            else:
                return match["country"]["names"]["en"]
        except:
            traceback.print_exc()
            return None
