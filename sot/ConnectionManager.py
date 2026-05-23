import os
import threading
import time
import traceback
import uuid
from collections import deque
from time import monotonic_ns

import maxminddb as mmdb
import pydivert
from events import EventManager

from .ip_location_overrides import (
    MATCHMAKING_OVERRIDE_MARKER,
    OVERRIDE_MARKER,
    LocationResult,
    apply_location_override,
    format_location,
    get_location_region_key,
)
from .net_utils import is_private_or_local_address
from .Region import region_from_name

MATCH_IDLE_SECONDS = 20
REGION_DELAY_SECONDS = 0.5
DISCONNECT_COOLDOWN_NS = 5 * 1_000_000_000


class ConnectionManager:
    class DelayedPacket:
        def __init__(self, packet, send_at: float):
            self.packet = packet
            self.send_at = send_at

    def __init__(self, region="US East - Washington"):
        try:
            self.region = region_from_name(region)
            print(
                "Region:",
                self.region,
                "City:",
                self.region.city,
                "Country:",
                self.region.country,
                "Shorthand:",
                self.region.shorthand,
            )
            self.events = EventManager(events=["join"])
            self.disconnect = False
            self.force_disconnect = False
            self.timeout = 0
            self.portspike = False

            self.is_stopped = threading.Event()
            self.delayed_packets = deque()
            self._delay_lock = threading.Lock()
            self._matchmaking_override_lock = threading.Lock()
            self._matchmaking_overrides = set()
            self._winDivert = None
            self._winMonitor = None
            self._match_state_lock = threading.Lock()
            self._match_game_server = None
            self._match_management_server = None
            self._match_id = None
            self._match_last_gs_time = None
            self._match_last_packet_time = None

            mmdb_folder = os.path.join(os.environ["LOCALAPPDATA"], "SpikingTool", "mmdb")
            self.mmlocation = os.path.join(mmdb_folder, os.listdir(mmdb_folder)[0])
            self.reader = mmdb.Reader(self.mmlocation)
            self.reader_lock = threading.Lock()

            self.thread_divert = threading.Thread(target=self._divert_SoT, daemon=True)
            self.thread_monitor = threading.Thread(target=self._monitor_SoT, daemon=True)
            self.thread_delay_sender = threading.Thread(
                target=self._delayed_sender, daemon=True
            )
            self.thread_divert.start()
            self.thread_monitor.start()
            self.thread_delay_sender.start()
            print("Listening for SoT packets...")
        except Exception:
            traceback.print_exc()

    def _should_drop_packet(self) -> bool:
        if self.force_disconnect:
            return True
        if self.disconnect:
            if monotonic_ns() - self.timeout > DISCONNECT_COOLDOWN_NS:
                self.disconnect = False
            else:
                return True
        return False

    def resolve_location(self, addr: str) -> LocationResult:
        with self.reader_lock:
            try:
                match = self.reader.get(addr)
            except Exception:
                match = self.reader.get("0.0.0.0")
        location = apply_location_override(addr, match)
        if location.is_override:
            print(
                f"GeoIP override: {location.override_name} | {addr} | "
                f"{location.raw.city}, {location.raw.country} -> "
                f"{location.city}, {location.country}"
            )
        return location

    def update_matchmaking_override_state(self, addr: str, location: LocationResult):
        region_key = get_location_region_key(location)
        if location.is_override:
            with self._matchmaking_override_lock:
                self._matchmaking_overrides.add(region_key)
            print(
                f"Matchmaking override recorded: {location.override_name} | "
                f"{addr} | {location.city}, {location.country}"
            )
        else:
            with self._matchmaking_override_lock:
                had_override = region_key in self._matchmaking_overrides
                if had_override:
                    self._matchmaking_overrides.remove(region_key)
            if had_override:
                print(
                    f"Matchmaking override cleared: {addr} | "
                    f"{location.city}, {location.country}"
                )

    def has_matchmaking_override(self, location: LocationResult) -> bool:
        region_key = get_location_region_key(location)
        with self._matchmaking_override_lock:
            return region_key in self._matchmaking_overrides

    def build_display_location(self, location: LocationResult) -> str:
        markers = []
        if self.has_matchmaking_override(location):
            markers.append(MATCHMAKING_OVERRIDE_MARKER)
        if location.is_override:
            markers.append(OVERRIDE_MARKER)
        return format_location(location.city, location.country, markers)

    def generate_match_id(self) -> str:
        return uuid.uuid4().hex

    def forget_last_match(self):
        """Clear match detection state so the next management server emits join again."""
        with self._match_state_lock:
            self._match_game_server = None
            self._match_management_server = None
            self._match_id = None
            self._match_last_gs_time = None
            self._match_last_packet_time = None
        print("Match state cleared — waiting for next management server")

    def _log_match(self, match_type: str, match_id: str, addr: str, port: int, display_location: str, match_text: str):
        print(f"[match:{match_type}] id={match_id} {addr}:{port} location={display_location}")
        for line in match_text.splitlines():
            print(f"  {line}")

    def _packet_mgmt(self):
        """Process outbound packets on port 3075; delay non-preferred regions."""
        while not self.is_stopped.is_set():
            try:
                packet = self._winDivert.recv()
            except OSError:
                print("WinDivert closed, stopping packet management")
                return
            except Exception:
                traceback.print_exc()
                continue

            if self._should_drop_packet():
                continue

            if not packet.is_outbound or not packet.dst_addr:
                continue

            location = self.resolve_location(packet.dst_addr)
            location_name = location.city
            if location_name == "Unknown":
                location_name = location.country

            print(f"Connecting to {self.build_display_location(location)} ({packet.dst_addr})")
            self.update_matchmaking_override_state(packet.dst_addr, location)

            if location_name == self.region.city:
                print(f"Preferred: {location_name} | {packet.dst_addr}")
                try:
                    self._winDivert.send(packet)
                except Exception:
                    traceback.print_exc()
            else:
                print(f"Not preferred: {location_name} | {packet.dst_addr}")
                send_at = time.monotonic() + REGION_DELAY_SECONDS
                with self._delay_lock:
                    self.delayed_packets.append(self.DelayedPacket(packet, send_at))

    def _connection_monitor(self):
        """
        Watch UDP 30000–32000 for game and management server endpoints.

        First new public endpoint → game server (logged locally only).
        Second distinct endpoint within 20s → management server; emitted via join.
        """
        while not self.is_stopped.is_set():
            try:
                packet = self._winMonitor.recv()
            except OSError:
                print("WinMonitor closed, stopping packet monitoring")
                return
            except Exception:
                traceback.print_exc()
                continue

            if self.is_stopped.is_set():
                return

            if self._should_drop_packet():
                continue

            if packet.payload is None:
                try:
                    self._winMonitor.send(packet)
                except Exception:
                    traceback.print_exc()
                continue

            if packet.direction == pydivert.Direction.INBOUND:
                addr = packet.src_addr
                port = packet.src_port
            else:
                addr = packet.dst_addr
                port = packet.dst_port

            if is_private_or_local_address(addr):
                try:
                    self._winMonitor.send(packet)
                except Exception:
                    traceback.print_exc()
                continue

            current = f"{addr}:{port}"
            now = time.monotonic()
            emit_join = False

            with self._match_state_lock:
                game_server = self._match_game_server
                management_server = self._match_management_server
                match_id = self._match_id
                last_gs_time = self._match_last_gs_time
                last_packet_time = self._match_last_packet_time

                new_activity = (
                    current != game_server
                    and current != management_server
                ) or last_packet_time is None or (now - last_packet_time) > MATCH_IDLE_SECONDS

                if new_activity:
                    if (
                        management_server is not None
                        or (game_server is None and management_server is None)
                        or last_gs_time is None
                        or (now - last_gs_time) > MATCH_IDLE_SECONDS
                    ):
                        self._match_management_server = None
                        match_id = self.generate_match_id()
                        self._match_id = match_id
                        self._match_game_server = current
                        self._match_last_gs_time = now
                        match_type = "game"
                        location = self.resolve_location(addr)
                        display_location = self.build_display_location(location)
                        match_text = f"Game server:\n{display_location}\n{current}"
                        self._log_match(
                            match_type, match_id, addr, port, display_location, match_text
                        )
                    else:
                        self._match_management_server = current
                        match_type = "management"
                        location = self.resolve_location(addr)
                        display_location = self.build_display_location(location)
                        match_text = (
                            f"Management server:\n{display_location}\n{current}"
                        )
                        self._log_match(
                            match_type, match_id, addr, port, display_location, match_text
                        )
                        emit_join = True

                self._match_last_packet_time = now

            if emit_join:
                try:
                    self.events.join(addr, port)  # pylint: disable=no-member
                except Exception:
                    traceback.print_exc()
                if self.portspike:
                    self.disconnect = True
                    self.timeout = monotonic_ns()
            try:
                self._winMonitor.send(packet)
            except Exception:
                traceback.print_exc()

    def _divert_SoT(self):
        while not self.is_stopped.is_set():
            try:
                self._winDivert = pydivert.WinDivert("udp.DstPort == 3075")
                time.sleep(1)
                self._winDivert.open()
                print("WinDivert opened successfully")
                break
            except Exception:
                traceback.print_exc()
                time.sleep(1)

        self._packet_mgmt()

        if self._winDivert and self._winDivert.is_open:
            try:
                self._winDivert.close()
            except Exception:
                pass

    def _monitor_SoT(self):
        while not self.is_stopped.is_set():
            try:
                self._winMonitor = pydivert.WinDivert(
                    "udp.DstPort >= 30000 and udp.DstPort <= 32000"
                )
                time.sleep(1)
                self._winMonitor.open()
                print("WinMonitor opened successfully")
                break
            except Exception:
                traceback.print_exc()
                time.sleep(1)

        self._connection_monitor()

        if self._winMonitor and self._winMonitor.is_open:
            try:
                self._winMonitor.close()
            except Exception:
                pass

    def _delayed_sender(self):
        while not self.is_stopped.is_set():
            if self._winDivert is None:
                time.sleep(0.1)
                continue

            due_packets = []
            with self._delay_lock:
                now = time.monotonic()
                while self.delayed_packets and self.delayed_packets[0].send_at <= now:
                    due_packets.append(self.delayed_packets.popleft())

            for entry in due_packets:
                try:
                    self._winDivert.send(entry.packet)
                except Exception:
                    traceback.print_exc()

            time.sleep(0.05)

    def getServerInfo(self, ip):
        try:
            location = self.resolve_location(ip)
            if location.city != "Unknown":
                return location.city
            return location.country
        except Exception:
            traceback.print_exc()
            return None
