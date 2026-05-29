class Region:
    def __init__(self, city, country, shorthand, active=True):
        self.city = city
        self.country = country
        self.shorthand = shorthand
        self.active = active


def region_from_name(name):
    return core_regions[name]


_ASA_CORE_REGIONS = {
    "US East - Washington DC (NY)": Region("Washington", "United States", "US-East", True),
    "US East - Virginia (Florida)": Region("Boydton", "United States", "US-East", True),
    "US Central - Chicago": Region("Chicago", "United States", "US-C", False),
    "US Central - Iowa": Region("Des Moines", "United States", "US-C", True),
    "Cheyenne": Region("Cheyenne", "United States", "US-C", False),
    "US South - Dallas": Region("San Antonio", "United States", "US-S", True),
    "US West - LA/LV": Region("San Jose", "United States", "US-W", True),
    "Brazil": Region("Campinas", "Brazil", "BR", True),
    "Dublin": Region("Dublin", "Ireland", "EU-W", False),
    "London": Region("London", "United Kingdom", "EU-W", True),
    "Amsterdam": Region("Amsterdam", "Netherlands", "EU-C", True),
    "Paris": Region("Paris", "France", "EU-W", True),
    "Sweden": Region("Sweden", "Sweden", "EU-C", True),
    "Johannesburg": Region("Johannesburg", "South Africa", "AF", True),
    "Dubai": Region("Dubai", "United Arab Emirates", "ME", False),
    "Pune": Region("Pune", "India", "IN", True),
    "Singapore": Region("Singapore", "Singapore", "SG", True),
    "Hong Kong (Honk Honk)": Region("Hong Kong", "Hong Kong", "HK", True),
    "Tokyo": Region("Tokyo", "Japan", "JP", True),
    "Osaka": Region("Osaka", "Japan", "JP", False),
    "Seoul": Region("Seoul", "South Korea", "KR", False),
    "Sydney": Region("Sydney", "Australia", "OCE", True),
    "Melbourne": Region("Melbourne", "Australia", "OCE", False),
}


def _build_core_regions() -> dict[str, Region]:
    ordered: dict[str, Region] = {}
    for name, region in _ASA_CORE_REGIONS.items():
        if region.active:
            ordered[name] = region
    for name, region in _ASA_CORE_REGIONS.items():
        if not region.active:
            ordered[f"{name} (debug)"] = region
    return ordered


core_regions = _build_core_regions()
