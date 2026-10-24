"""Address -> lat/lng. The seeded Coimbatore area table first (instant, offline), then Nominatim, cached."""

import hashlib
import json
import logging
import urllib.parse
import urllib.request

from sqlalchemy.orm import Session

from ..config import settings
from ..models import ExtractionCache
from ..seed.venues import AREAS

log = logging.getLogger("showup.geocode")
NOMINATIM = "https://nominatim.openstreetmap.org/search"


def from_table(text: str) -> dict | None:
    low = (text or "").lower()
    # Longest name first so "RS Puram" wins over a shorter accidental match.
    for area in sorted(AREAS, key=lambda a: -len(a["name"])):
        if area["name"].lower() in low:
            return area
    return None


def geocode(db: Session, address: str) -> dict | None:
    if not address or not address.strip():
        return None
    hit = from_table(address)
    if hit:
        return {"lat": hit["lat"], "lng": hit["lng"], "area": hit["name"]}
    if settings.app_env == "test":
        return None

    key = "geocode:" + hashlib.sha256(address.strip().lower().encode()).hexdigest()
    cached = db.get(ExtractionCache, key)
    if cached:
        return cached.result or None
    query = address if "coimbatore" in address.lower() else f"{address}, Coimbatore"
    url = f"{NOMINATIM}?{urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'in'})}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShowUp/0.1 (student events pilot)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = json.load(resp)
        result = {"lat": float(rows[0]["lat"]), "lng": float(rows[0]["lon"]), "area": None} if rows else {}
    except Exception as e:  # offline, rate-limited, bad response: fall back to no coordinates
        log.info("Geocoding failed for %r: %s", address, e)
        return None
    db.add(ExtractionCache(key=key, result=result))
    db.commit()
    return result or None
