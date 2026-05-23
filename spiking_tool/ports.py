from __future__ import annotations

from typing import Any, Optional, Tuple, Union


def normalize_port_digits(status: Union[int, str]) -> str:
    """Extract last three port digits from a join status value."""
    port = int(str(status)[2:])
    port_str = str(port)
    if len(port_str) < 3:
        return "0" * (3 - len(port_str)) + port_str
    return port_str


def format_client_status(
    status: Any, current_port: Optional[str]
) -> Tuple[str, Optional[str]]:
    """
    Normalize status for the controller client table.

    Returns (display_status, updated_port).
    """
    port = current_port
    display = status

    if isinstance(status, int):
        port = normalize_port_digits(status)
        display = port

    if "outpost=" in str(display):
        location = str(display).replace("outpost=", "")
        display = f"{port} -- {location}"

    return str(display), port
