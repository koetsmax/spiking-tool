class Region:
    def __init__(self, city, country, name):
        self.city = city
        self.country = country
        self.name = name

    def fromName(name):
        return Region(
            Region._regions[name]["City"], Region._regions[name]["Country"], name
        )

    def getRegions():
        return list(Region._regions.keys())

    _regions = {
        "Singapore": {
            "LongName": "Singapore",
            "ShortName": "SG",
            "City": "Singapore",
            "Country": "Singapore",
            "Location": {"Latitude": 1.3521, "Longitude": 103.8198},
        },
        "OCE": {
            "LongName": "Oceania (Sydney)",
            "ShortName": "OCE",
            "City": "Syndey",
            "Country": "Australia",
            "Location": {"Latitude": -33.8688, "Longitude": 151.2093},
        },
        "Brazil": {
            "LongName": "Brazil (Campinas)",
            "ShortName": "BR",
            "City": "Campinas",
            "Country": "Brazil",
            "Location": {"Latitude": -22.9068, "Longitude": -47.0626},
        },
        "China": {
            "LongName": "China (Hong Kong)",
            "ShortName": "CN",
            "City": "Hong Kong",
            "Country": "China",
            "Location": {"Latitude": 22.3964, "Longitude": 114.1095},
        },
        "Japan": {
            "LongName": "Japan (Tokyo)",
            "ShortName": "JP",
            "City": "Tokyo",
            "Country": "Japan",
            "Location": {"Latitude": 35.6895, "Longitude": 139.6917},
        },
        "EU Central": {
            "LongName": "EU Central (Amsterdam)",
            "ShortName": "EU-C",
            "City": "Amsterdam",
            "Country": "Netherlands",
            "Location": {"Latitude": 52.3702, "Longitude": 4.8952},
        },
        "EU West": {
            "LongName": "EU West (Dublin)",
            "ShortName": "EU-W",
            "City": "Dublin",
            "Country": "Ireland",
            "Location": {"Latitude": 53.3498, "Longitude": -6.2603},
        },
        "US South (Dallas)": {
            "LongName": "US South (Dallas)",
            "ShortName": "US-S",
            "City": "San Antonio",
            "Country": "United States",
            "Location": {"Latitude": 29.4241, "Longitude": -98.4936},
        },
        "US East (NY/NJ)": {
            "LongName": "US East (New York/New Jersey)",
            "ShortName": "US-E",
            "City": "Washington",
            "Country": "United States",
            "Location": {"Latitude": 38.9072, "Longitude": -77.0369},
        },
        "US West (LA/LV)": {
            "LongName": "US West (Los Angeles/Las Vegas)",
            "ShortName": "US-W",
            "City": "San Jose",
            "Country": "United States",
            "Location": {"Latitude": 37.3382, "Longitude": -121.8863},
        },
        "US Central (Chicago)": {
            "LongName": "US Central (Chicago)",
            "ShortName": "US-C",
            "City": "Chicago",
            "Country": "United States",
            "Location": {"Latitude": 41.8781, "Longitude": -87.6298},
        },
    }
