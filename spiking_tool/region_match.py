"""Compare detected match regions against the controller region selection."""

from __future__ import annotations

from sot.Region import region_from_name
from sot.ip_location_overrides import (
    MATCHMAKING_OVERRIDE_MARKER,
    OVERRIDE_MARKER,
    format_location,
)

from spiking_tool.match import MatchDetails


def normalize_match_region(region: str) -> str:
    text = region
    for marker in (MATCHMAKING_OVERRIDE_MARKER, OVERRIDE_MARKER):
        text = text.replace(f" ({marker})", "").replace(marker, "")
    return text.strip()


def match_in_selected_region(match: MatchDetails, region_key: str) -> bool:
    selected = region_from_name(region_key)
    expected = format_location(selected.city, selected.country, [])
    return normalize_match_region(match.region) == expected
