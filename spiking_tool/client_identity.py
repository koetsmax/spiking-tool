"""Display-name assignment when multiple clients share the same config name."""

from __future__ import annotations

import re
from typing import Protocol


class _NamedClient(Protocol):
    name: str
    display_name: str


def assign_display_name(existing_clients: list[_NamedClient], base_name: str) -> str:
    """
    Pick a unique display name for a new connection.

    One client keeps ``base_name``; when a second connects, the first becomes
    ``base_name (1)`` and the new one ``base_name (2)``, etc.
    """
    same_base = [client for client in existing_clients if client.name == base_name]
    if len(same_base) == 1 and same_base[0].display_name == base_name:
        same_base[0].display_name = f"{base_name} (1)"
    if same_base:
        return f"{base_name} ({len(same_base) + 1})"
    return base_name


def sort_display_name_key(display_name: str) -> tuple[str, int]:
    match = re.match(r"^(.+?) \((\d+)\)$", display_name)
    if match:
        return (match.group(1), int(match.group(2)))
    return (display_name, 0)
