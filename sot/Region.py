class Region:
    def __init__(self, city, country, shorthand):
        self.city = city
        self.country = country
        self.shorthand = shorthand  # This isn't really used, not from DB


def region_from_name(name):
    return core_regions[name]


core_regions = {
    "US East - Washington": Region("Washington", "United States", "US-East"),
    "US East - VA": Region("Boydton", "United States", "US-East2"),
    "US Central - Chicago": Region("Chicago", "United States", "US-C"),
    "US Central - Iowa": Region("Des Moines", "United States", "US-C"),
    "US South - Dallas": Region("San Antonio", "United States", "US-S"),
    "US West - LA/LV": Region("San Jose", "United States", "US-W"),
    "Brazil": Region("Campinas", "Brazil", "BR"),
    "Dublin": Region("Dublin", "Ireland", "EU-W"),
    "Amsterdam": Region("Amsterdam", "Netherlands", "EU-C"),
    "Dubai": Region("Dubai", "United Arab Emirates", "ME"),
    "Singapore": Region("Singapore", "Singapore", "SG"),
    "Hong Kong": Region("Hong Kong", "Hong Kong", "HK"),
    "Tokyo": Region("Tokyo", "Japan", "JP1"),
    "Osaka": Region("Osaka", "Japan", "JP2"),
    "Sydney": Region("Sydney", "Australia", "OCE1"),
    "Melbourne": Region("Melbourne", "Australia", "OCE2"),
}
