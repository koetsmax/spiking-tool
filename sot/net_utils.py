import ipaddress
from typing import Optional


def is_private_or_local_address(addr: Optional[str]) -> bool:
    """Return True if `addr` is private/local and should be ignored."""
    if not addr:
        return False
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)
