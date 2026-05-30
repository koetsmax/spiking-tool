from __future__ import annotations

from typing import Any, Optional, Tuple, Union


def extract_port_from_status(status: str) -> Optional[str]:
    """Return the three-digit port prefix from statuses like ``546 - Loaded``."""
    if len(status) >= 5 and status[3:6] == " - " and status[:3].isdigit():
        return status[:3]
    return None


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
        elif current_status == "Waiting to load" or (
            isinstance(current_status, str) and current_status.endswith(" - Waiting to load")
        ):
            display = f"{port} - Waiting to load"
        else:
            display = port
    elif isinstance(status, str):
        extracted = extract_port_from_status(status)
        if extracted is not None:
            port = extracted

    return str(display), port
