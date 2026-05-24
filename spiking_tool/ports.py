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
    status: Any,
    current_port: Optional[str],
    *,
    current_status: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Normalize status for the controller client table.

    Returns (display_status, updated_port).
    """
    port = current_port
    display = status

    if isinstance(status, int):
        port = normalize_port_digits(status)
        if current_status == "Awaiting connection":
            display = f"{port} - awaiting connection"
        else:
            display = port

    return str(display), port
