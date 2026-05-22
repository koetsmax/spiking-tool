import ipaddress
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

UNKNOWN_LOCATION = "Unknown"
OVERRIDE_MARKER = "O"
MATCHMAKING_OVERRIDE_MARKER = "MO"


@dataclass(frozen=True)
class RawLocation:
    city: str
    country: str
    country_iso: str
    registered_country_iso: str


@dataclass(frozen=True)
class LocationOverrideRule:
    name: str
    corrected_city: str
    corrected_country: str
    corrected_country_iso: str
    match_country: Optional[str] = None
    match_country_iso: Optional[str] = None
    match_registered_country_iso: Optional[str] = None
    match_city: Optional[str] = None
    require_unknown_city: bool = False
    unconditional: bool = False


@dataclass(frozen=True)
class LocationResult:
    city: str
    country: str
    raw: RawLocation
    country_iso: str
    override_name: Optional[str] = None

    @property
    def is_override(self) -> bool:
        return self.override_name is not None


DEFAULT_LOCATION_OVERRIDE_RULES: dict[str, LocationOverrideRule] = {
    "135.236.0.0/17": LocationOverrideRule(
        name="azure_135_236_0_0_17_amsterdam",
        corrected_city="Amsterdam",
        corrected_country="Netherlands",
        corrected_country_iso="NL",
        match_country="United Kingdom",
        match_country_iso="GB",
        require_unknown_city=True,
    ),
}


def get_nested_text(record: Optional[Mapping], path: Iterable[str]) -> str:
    current: Any = record
    for key in path:
        if not isinstance(current, Mapping):
            return UNKNOWN_LOCATION
        current = current.get(key)
    if isinstance(current, str) and current:
        return current
    return UNKNOWN_LOCATION


def raw_location_from_mmdb(record: Optional[Mapping]) -> RawLocation:
    return RawLocation(
        city=get_nested_text(record, ("city", "names", "en")),
        country=get_nested_text(record, ("country", "names", "en")),
        country_iso=get_nested_text(record, ("country", "iso_code")),
        registered_country_iso=get_nested_text(
            record, ("registered_country", "iso_code")
        ),
    )


def _is_unknown(value: str) -> bool:
    return value.strip().lower() in {"", UNKNOWN_LOCATION.lower()}


def _matches_expected(actual: str, expected: Optional[str]) -> bool:
    if expected is None:
        return True
    return actual == expected


def normalize_region_text(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return " ".join(normalized.split())


def get_location_region_key(location: LocationResult) -> tuple[str, str]:
    country_key = location.country_iso
    if _is_unknown(country_key):
        country_key = normalize_region_text(location.country)
    return (normalize_region_text(location.city), country_key.upper())


def _ip_in_cidr(addr: str, cidr_block: str) -> bool:
    return ipaddress.ip_address(addr) in ipaddress.ip_network(cidr_block)


def _rule_matches(raw: RawLocation, rule: LocationOverrideRule) -> bool:
    if rule.unconditional:
        return True
    if rule.require_unknown_city and not _is_unknown(raw.city):
        return False
    return (
        _matches_expected(raw.city, rule.match_city)
        and _matches_expected(raw.country, rule.match_country)
        and _matches_expected(raw.country_iso, rule.match_country_iso)
        and _matches_expected(raw.registered_country_iso, rule.match_registered_country_iso)
    )


def apply_location_override(
    addr: Optional[str],
    record: Optional[Mapping],
    rules: Optional[dict[str, LocationOverrideRule]] = None,
) -> LocationResult:
    if rules is None:
        rules = DEFAULT_LOCATION_OVERRIDE_RULES
    raw = raw_location_from_mmdb(record)
    if addr is None:
        return LocationResult(
            city=raw.city,
            country=raw.country,
            raw=raw,
            country_iso=raw.country_iso,
        )
    for cidr_block, rule in rules.items():
        if _ip_in_cidr(addr, cidr_block) and _rule_matches(raw, rule):
            return LocationResult(
                city=rule.corrected_city,
                country=rule.corrected_country,
                raw=raw,
                country_iso=rule.corrected_country_iso,
                override_name=rule.name,
            )
    return LocationResult(
        city=raw.city,
        country=raw.country,
        raw=raw,
        country_iso=raw.country_iso,
    )


def format_location(city: str, country: str, markers: Optional[Iterable[str]] = None) -> str:
    marker_text = "".join(f" ({marker})" for marker in (markers or []))
    return f"{city}, {country}{marker_text}"
