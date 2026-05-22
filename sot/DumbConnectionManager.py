import threading
import traceback
import pydivert


class DumbConnectionManager:
    def __init__(self):
        try:
            self.force_disconnect = False
            self.send_lock = threading.Lock()

            self.divertThread = threading.Thread(target=self._divert_SoT)
            self.divertThread.start()
        except:
            traceback.print_exc()

    def _divert_SoT(self):
        self._winDivert = pydivert.WinDivert(
            "outbound and (udp.DstPort == 3075 or (udp.DstPort >= 30000 and udp.DstPort < 31000))"
        )
        self._winDivert.open()
        self.timeout = 0
        print("Listening for SoT packets...")

        while True:
            try:
                packet = self._winDivert.recv()
                try:
                    if self.force_disconnect:
                        continue

                except:
                    traceback.print_exc()
                with self.send_lock:
                    self._winDivert.send(packet)  # re-inject the packet into the network stack
            except Exception as e:
                traceback.print_exc()
