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
    "US South - Dallas": Region("San Antonio", "United States", "US-S"),  # Dallas
    "US West - LA/LV": Region("San Jose", "United States", "US-W"),
    "Europe - Amsterdam": Region("Amsterdam", "Netherlands", "EU-C"),
    "Europe - United Kingdom": Region("Dublin", "Ireland", "EU-W"),
    "Singapore": Region("Singapore", "Singapore", "SG"),
    "Hong Kong": Region("Central", "Hong Kong", "CN"),
    "Japan": Region("Tokyo", "Japan", "JP"),
    "Sydney": Region("Sydney", "Australia", "OCE"),
    "Brazil": Region("Campinas", "Brazil", "BR"),
}
