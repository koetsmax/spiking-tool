"""AFK status payloads shared between client and controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

AfkStatusType = Literal["text", "countdown", "error", "clear"]
CountdownMode = Literal["seconds", "duration", "compact"]

SLEEP_STATUS_PREFIX = "Sleeping for"


def format_duration(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    minutes, secs = divmod(abs(seconds), 60)
    if minutes:
        body = f"{minutes} minute{'s' if minutes != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
    else:
        body = f"{secs} second{'s' if abs(secs) != 1 else ''}"
    return f"{sign}{body}"


def format_compact_time(seconds: int) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    if minutes and secs:
        return f"{minutes}m {secs}s"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def format_elapsed(seconds: int) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return " ".join(parts)


def format_countdown_display(
    remaining_seconds: int,
    *,
    prefix: str = SLEEP_STATUS_PREFIX,
    mode: CountdownMode = "seconds",
    cycle: int | None = None,
) -> str:
    cycle_part = f"({cycle}) " if cycle is not None else ""
    label = prefix.strip() or SLEEP_STATUS_PREFIX
    if mode == "compact":
        return f"{cycle_part}{label} {format_compact_time(remaining_seconds)}"
    if mode == "duration":
        return f"{cycle_part}{label} {format_duration(remaining_seconds)}"
    secs_label = "second" if remaining_seconds == 1 else "seconds"
    return f"{cycle_part}{label} {remaining_seconds} {secs_label}"


@dataclass(frozen=True)
class AfkStatusPayload:
    type: AfkStatusType
    message: str = ""
    prefix: str = ""
    seconds: int = 0
    mode: CountdownMode = "seconds"
    cycle: int | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.type == "countdown":
            payload["prefix"] = self.prefix
            payload["seconds"] = self.seconds
            payload["mode"] = self.mode
        elif self.type in ("text", "error"):
            payload["message"] = self.message
        if self.cycle is not None:
            payload["cycle"] = self.cycle
        return payload

    @classmethod
    def from_payload(cls, data: Mapping[str, Any] | str | None) -> "AfkStatusPayload | None":
        if data is None:
            return None
        if isinstance(data, str):
            if not data:
                return cls(type="clear")
            return cls(type="text", message=data)
        status_type = data.get("type", "text")
        if status_type == "clear":
            return cls(type="clear")
        if status_type == "countdown":
            cycle = data.get("cycle")
            return cls(
                type="countdown",
                prefix=str(data.get("prefix", "")),
                seconds=int(data.get("seconds", 0)),
                mode=data.get("mode", "seconds"),
                cycle=int(cycle) if cycle is not None else None,
            )
        if status_type == "error":
            cycle = data.get("cycle")
            return cls(
                type="error",
                message=str(data.get("message", "Unknown AFK error")),
                cycle=int(cycle) if cycle is not None else None,
            )
        cycle = data.get("cycle")
        return cls(
            type="text",
            message=str(data.get("message", "")),
            cycle=int(cycle) if cycle is not None else None,
        )

    def _cycle_prefix(self) -> str:
        return f"({self.cycle}) " if self.cycle is not None else ""

    def display_text(self, *, remaining_seconds: int | None = None) -> str:
        if self.type == "clear":
            return ""
        if self.type == "countdown":
            remaining = self.seconds if remaining_seconds is None else remaining_seconds
            return format_countdown_display(
                remaining,
                prefix=self.prefix,
                mode=self.mode,
                cycle=self.cycle,
            )
        if self.type == "error":
            body = self.message if self.message.startswith("Error:") else f"Error: {self.message}"
            return f"{self._cycle_prefix()}{body}"
        return f"{self._cycle_prefix()}{self.message}"

    def log_text(self, *, remaining_seconds: int | None = None) -> str:
        return self.display_text(remaining_seconds=remaining_seconds)
