class Region:
    def __init__(self, city, country, shorthand):
        self.city = city
        self.country = country
        self.shorthand = shorthand


def region_from_name(name):
    return core_regions[name]


core_regions = {
    "US East - NY/NJ": Region("Tappahannock", "United States", "US-E"),
    "US Central - Chicago": Region("Chicago", "United States", "US-C"),
    "US South - Dallas": Region("San Antonio", "United States", "US-S"),
    "US Midwest - Des Moines": Region("Des Moines", "United States", "US-MW"),
    "US West - LA/LV": Region("San Jose", "United States", "US-W"),
    "Brazil": Region("Campinas", "Brazil", "BR"),
    "Europe - Amsterdam": Region("Amsterdam", "Netherlands", "EU-C"),
    "Europe - United Kingdom": Region("Dublin", "Ireland", "EU-W"),
    "Dubai": Region("Dubai", "United Arab Emirates", "UAE"),
    "South Africa": Region("Johannesburg", "South Africa", "ZA"),
    "Singapore": Region("Singapore", "Singapore", "SG"),
    "Hong Kong": Region("Hong Kong", "Hong Kong", "HK"),
    "Japan - Tokyo": Region("Tokyo", "Japan", "JP1"),
    "Japan - Osaka": Region("Osaka", "Japan", "JP2"),
    "Australia - Sydney": Region("Sydney", "Australia", "OCE1"),
    "Australia - Melbourne": Region("Melbourne", "Australia", "OCE2"),
}
