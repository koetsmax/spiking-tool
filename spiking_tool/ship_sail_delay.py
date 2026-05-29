"""Staggered delays before clients press sail based on ship type."""

from __future__ import annotations

SHIP_MENU_ORDER = {
    "Galleon": 0,
    "Captaincy": 0,
    "Brigantine": 1,
    "Sloop": 2,
}

DEFAULT_SHIP_SAIL_COOLDOWNS = {
    "Galleon": 5.0,
    "Brigantine": 5.0,
    "Sloop": 5.0,
}


def compute_sail_delay(
    ship_type: str,
    fleet_ship_types: list[str],
    cooldowns: dict[str, float] | None = None,
) -> float:
    """
    Seconds to wait before this client sails.

    Ships with a larger crew size sail immediately and smaller ships
    wait for the configured cooldown of each ship type ahead of them.
    """
    merged = {**DEFAULT_SHIP_SAIL_COOLDOWNS, **(cooldowns or {})}
    fleet = {ship for ship in fleet_ship_types if ship in SHIP_MENU_ORDER}
    if not fleet:
        return 0.0
    if fleet == {"Sloop"}:
        return 0.0

    my_rank = SHIP_MENU_ORDER.get(ship_type, 0)
    delay = 0.0
    for other_ship in fleet:
        if other_ship == ship_type:
            continue
        other_rank = SHIP_MENU_ORDER.get(other_ship, 0)
        if other_rank < my_rank:
            delay = max(delay, merged.get(other_ship, 0.0))
    return delay
