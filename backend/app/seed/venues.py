"""Coimbatore area lookup, so onboarding and seeding work without a geocoder."""

AREAS: list[dict] = [
    {"name": "Gandhipuram", "lat": 11.0168, "lng": 76.9675},
    {"name": "Peelamedu", "lat": 11.0247, "lng": 77.0028},
    {"name": "Saravanampatti", "lat": 11.0790, "lng": 76.9990},
    {"name": "RS Puram", "lat": 11.0089, "lng": 76.9496},
    {"name": "Singanallur", "lat": 11.0004, "lng": 77.0283},
    {"name": "Race Course", "lat": 11.0006, "lng": 76.9741},
    {"name": "Ganapathy", "lat": 11.0398, "lng": 76.9781},
    {"name": "Saibaba Colony", "lat": 11.0247, "lng": 76.9447},
    {"name": "Town Hall", "lat": 10.9936, "lng": 76.9614},
    {"name": "Ukkadam", "lat": 10.9877, "lng": 76.9614},
    {"name": "Kuniyamuthur", "lat": 10.9600, "lng": 76.9550},
    {"name": "Vadavalli", "lat": 11.0255, "lng": 76.9030},
    {"name": "Thudiyalur", "lat": 11.0790, "lng": 76.9420},
    {"name": "Kalapatti", "lat": 11.0750, "lng": 77.0400},
    {"name": "Hope College", "lat": 11.0260, "lng": 77.0170},
    {"name": "Avinashi Road", "lat": 11.0300, "lng": 77.0200},
    {"name": "Sulur", "lat": 11.0240, "lng": 77.1250},
    {"name": "Podanur", "lat": 10.9620, "lng": 76.9800},
]


def find_area(name: str) -> dict:
    return next(a for a in AREAS if a["name"] == name)
