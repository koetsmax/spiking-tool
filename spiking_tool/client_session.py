"""Client-side session state that survives server/controller disconnects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ClientSessionState:
    """Operational state the client keeps while reconnecting to the server."""

    connected_once: bool = False
    prev_port: Optional[int] = None
    region_name: str = "US East - Washington DC (NY)"
    portspike: bool = False
    ship_type: str = "Brigantine"
    last_status: Any = "Pending..."
    last_match: Optional[dict[str, Any]] = None
    last_afk_status: Optional[dict[str, Any]] = field(default=None, repr=False)

    def record_status(self, status: Any, *, match: Optional[dict[str, Any]] = None) -> None:
        self.last_status = status
        if match is not None:
            self.last_match = match

    def record_region(self, region_name: str) -> None:
        self.region_name = region_name

    def record_portspike(self, enabled: bool) -> None:
        self.portspike = enabled

    def record_ship(self, ship_type: str) -> None:
        self.ship_type = ship_type

    def record_afk_status(self, payload: dict[str, Any]) -> None:
        if payload.get("type") == "clear":
            self.last_afk_status = None
            return
        self.last_afk_status = dict(payload)
