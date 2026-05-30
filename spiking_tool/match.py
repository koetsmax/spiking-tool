from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from spiking_tool.ports import normalize_port_digits


@dataclass(frozen=True)
class MatchDetails:
    game_ip: str
    game_port: int
    management_ip: str
    management_port: int
    region: str

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> "MatchDetails":
        return cls(
            game_ip=str(data["game_ip"]),
            game_port=int(data["game_port"]),
            management_ip=str(data["management_ip"]),
            management_port=int(data["management_port"]),
            region=str(data["region"]),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "game_ip": self.game_ip,
            "game_port": self.game_port,
            "management_ip": self.management_ip,
            "management_port": self.management_port,
            "region": self.region,
        }

    @property
    def management_port_digits(self) -> str:
        return normalize_port_digits(self.management_port)

    def to_clipboard_text(self) -> str:
        return "Match found!\n" f"Region: {self.region}\n" f"{self.game_ip}:{self.game_port}\n" "\n" "Management server:\n" f"{self.management_ip}:{self.management_port}"
