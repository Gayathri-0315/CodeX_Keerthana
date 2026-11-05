"""Where is "PSG college" / "Tidel Park" / "Kovaipudur" / "Chennai"? For natural-language search.

Order: the Coimbatore area table (instant), then venues of real events on ShowUp (so "KCT" finds "KCT Tech
Park"), then the map (Nominatim, cached in the database; see services/geocode.py). Returns a display name
and a point; the caller filters events within a radius of it.
"""

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, ExtractionCache
from ..seed.venues import AREAS
from .travel import CITY_CENTER, haversine_km

log = logging.getLogger("showup.places")
NOMINATIM = "https://nominatim.openstreetmap.org/search"

CITY_WORDS = {"coimbatore", "kovai", "cbe", "covai", "coimbatore city"}
# Words that describe a kind of place rather than name it ("PSG college" -> "psg").
GENERIC = {"college", "colleges", "university", "campus", "the", "of", "and", "near", "park", "hall", "auditorium", "centre",
           "center", "mall", "road", "rd", "street", "st", "area", "institute", "school", "engineering", "technology", "tech",
           "arts", "science", "coimbatore", "kovai", "cbe"}
ALIASES = {"saravanampatty": "Saravanampatti", "saravanampati": "Saravanampatti", "r.s. puram": "RS Puram", "r s puram": "RS Puram",
           "r.s puram": "RS Puram", "racecourse": "Race Course", "townhall": "Town Hall", "sai baba colony": "Saibaba Colony",
           "avinashi rd": "Avinashi Road", "kalapatty": "Kalapatti"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2}


def _area(text: str) -> dict | None:
    low = " " + text.lower().strip() + " "
    for alias, name in ALIASES.items():
        if f" {alias} " in low:
            return next(a for a in AREAS if a["name"] == name)
    for a in sorted(AREAS, key=lambda a: -len(a["name"])):
        if re.search(rf"(?<![a-z]){re.escape(a['name'].lower())}(?![a-z])", low):
            return a
    return None


def _venue(db: Session, text: str) -> dict | None:
    """A venue of an event on ShowUp whose name (or address) contains every distinctive word asked for."""
    want = _words(text) - GENERIC
    if not want:
        return None
    rows = db.execute(select(Event.venue_name, Event.address, Event.lat, Event.lng).where(
        Event.status == "published", Event.lat.is_not(None), Event.venue_name.is_not(None))).all()
    for name, address, lat, lng in rows:
        if want <= _words(f"{name} {address or ''}"):
            return {"name": name, "lat": lat, "lng": lng, "kind": "venue"}
    return None


BIG = ("city", "town", "state", "county", "state_district", "district", "municipality")


def _lookup(db: Session, query: str) -> dict | None:
    """One Nominatim search, cached in the database (misses too)."""
    key = "place:" + hashlib.sha256(query.lower().encode()).hexdigest()
    cached = db.get(ExtractionCache, key)
    if cached is not None:
        return cached.result or None
    url = f"{NOMINATIM}?{urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'in'})}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShowUp/0.1 (student events; place search)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            rows = json.load(resp)
    except Exception as e:  # offline, slow or rate-limited: just "not found" (and don't cache it)
        log.info("Place lookup failed: %s", type(e).__name__)
        return None
    hit = {"lat": float(rows[0]["lat"]), "lng": float(rows[0]["lon"]), "type": rows[0].get("addresstype") or rows[0].get("type")} if rows else {}
    db.add(ExtractionCache(key=key, result=hit))
    db.commit()
    return hit or None


def _map(db: Session, text: str) -> dict | None:
    """A city or town anywhere in India by its own name ("Chennai"); otherwise a place inside Coimbatore."""
    if settings.app_env == "test":
        return None
    plain = _lookup(db, text)
    if plain and plain.get("type") in BIG:
        return {"lat": plain["lat"], "lng": plain["lng"], "kind": "city"}
    local = _lookup(db, f"{text}, Coimbatore")
    if local and haversine_km(CITY_CENTER[0], CITY_CENTER[1], local["lat"], local["lng"]) <= 40:
        return {"lat": local["lat"], "lng": local["lng"], "kind": "city" if local.get("type") in BIG else "map"}
    if plain and haversine_km(CITY_CENTER[0], CITY_CENTER[1], plain["lat"], plain["lng"]) <= 40:
        return {"lat": plain["lat"], "lng": plain["lng"], "kind": "map"}
    return None  # a small place far away is more likely a misreading than what they meant


def resolve(db: Session | None, text: str) -> dict | None:
    """-> {"name", "lat", "lng", "kind": city|area|venue|map} or None if we can't place it."""
    text = re.sub(r"\s+", " ", (text or "").strip(" .,!?'\""))[:80]
    if len(text) < 2:
        return None
    if text.lower() in CITY_WORDS:
        return {"name": "Coimbatore", "lat": CITY_CENTER[0], "lng": CITY_CENTER[1], "kind": "city"}
    if a := _area(text):
        return {"name": a["name"], "lat": a["lat"], "lng": a["lng"], "kind": "area"}
    if db is None:
        return None
    if v := _venue(db, text):
        return v
    if m := _map(db, text):
        return {**m, "name": " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in text.split())}
    return None


def radius_for(kind: str) -> int:
    return 20 if kind == "city" else 5
