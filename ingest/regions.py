"""Map UK cities to their region"""

CITY_TO_REGION = {
    "London": "London",
    "Southampton": "South East",
    "Bristol": "South West",
    "Manchester": "North West",
    "Liverpool": "North West",
    "Leeds": "Yorkshire and the Humber",
    "Sheffield": "Yorkshire and the Humber",
    "Birmingham": "West Midlands",
    "Nottingham": "East Midlands",
    "Leicester": "East Midlands",
    "Glasgow": "Scotland",
    "Edinburgh": "Scotland",
    "Cardiff": "Wales",
}


def region_for(city):
    """Return the region for a given city, or Unknown if not found."""
    return CITY_TO_REGION.get(city, "Unknown")