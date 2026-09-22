"""
Phase 10: Location grounding.

Instead of relying on the LLM to "know" Chennai geography (which failed
silently for "Meenambakkam" even though it's the airport's own neighbourhood),
this module geocodes any place name mentioned in an idea via OpenStreetMap
Nominatim and checks real-world distance to a short list of Chennai landmarks
that carry specific regulatory implications (airport, coastline, a couple of
heritage sites). Matches within a threshold produce DETERMINISTIC extra
constraint topics for validate.py -- not dependent on the LLM recognizing
the place name.
"""
import math
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "urban-planning-copilot-poc (educational demo)"

# Landmark -> (lat, lon, proximity threshold km, topic key, topic query)
# Threshold is deliberately generous (real clearance/regulation zones are
# often larger and irregularly shaped) -- this is a screening flag, not a
# precise legal boundary check.
LANDMARKS = [
    {
        "name": "Chennai International Airport",
        "lat": 12.9941, "lon": 80.1709,
        "radius_km": 6,
        "topic_key": "airport_clearance",
        "topic_query": "airport height restriction AAI NOC clearance",
    },
    {
        "name": "Marina Beach / Chennai coastline",
        "lat": 13.0500, "lon": 80.2824,
        "radius_km": 3,
        "topic_key": "coastal_regulation_zone",
        "topic_query": "coastal regulation zone CRZ construction restrictions",
    },
    {
        "name": "Fort St. George (heritage precinct)",
        "lat": 13.0800, "lon": 80.2870,
        "radius_km": 1,
        "topic_key": "heritage_conservation",
        "topic_query": "heritage conservation zone building restrictions",
    },
]

_geocode_cache = {}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(place_name: str):
    """Return (lat, lon) for a place name, biased to Chennai, or None if not found."""
    if not place_name or not place_name.strip():
        return None

    key = place_name.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]

    query = f"{place_name.strip()}, Chennai, India"
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  ! Geocoding failed for '{place_name}': {e}")
        return None
    finally:
        time.sleep(1)  # Nominatim usage policy: max 1 request/second

    if not results:
        _geocode_cache[key] = None
        return None

    coords = (float(results[0]["lat"]), float(results[0]["lon"]))
    _geocode_cache[key] = coords
    return coords


def nearby_landmark_topics(place_name: str) -> dict:
    """
    Geocode place_name and return {topic_key: topic_query} for any landmark
    within its regulatory-relevant radius. Empty dict if no place name, the
    geocoder can't resolve it, or nothing nearby matters.
    """
    coords = geocode(place_name)
    if coords is None:
        return {}

    lat, lon = coords
    topics = {}
    for landmark in LANDMARKS:
        dist = _haversine_km(lat, lon, landmark["lat"], landmark["lon"])
        if dist <= landmark["radius_km"]:
            topics[landmark["topic_key"]] = landmark["topic_query"]
            print(f"  Location check: '{place_name}' is {dist:.1f}km from {landmark['name']} -> flagging {landmark['topic_key']}")
    return topics


if __name__ == "__main__":
    import sys

    place = " ".join(sys.argv[1:]) or "Meenambakkam"
    coords = geocode(place)
    print(f"Geocoded '{place}' -> {coords}")
    print(f"Nearby-landmark topics: {nearby_landmark_topics(place)}")
