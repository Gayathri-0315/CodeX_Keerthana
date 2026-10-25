from .services.feed import Evaluated
from .timeutil import iso_utc

TRUST_LABELS = {"trusted": "Trusted organizer", "verified": "Verified organizer", "new": "New organizer"}


def registration_brief(reg) -> dict | None:
    """Just enough for a card or detail page to show the right button."""
    if reg is None:
        return None
    return {"id": reg.id, "status": reg.status, "waitlist_position": reg.waitlist_position,
            "promotion_expires_at": iso_utc(reg.promotion_expires_at), "external": reg.external}


def event_card(ev: Evaluated, seats_taken: int, saved: bool, reg: dict | None = None) -> dict:
    """What a feed card needs. Cards show the first three reasons."""
    e, r, s = ev.event, ev.result, ev.scored
    return {
        "registration": reg,
        "id": e.id,
        "title": e.title,
        "category": e.category,
        "tags": e.tags,
        "mode": e.mode,
        "venue_name": e.venue_name,
        "start_at": iso_utc(e.start_at),
        "end_at": iso_utc(e.end_at),
        "fee_inr": e.fee_inr,
        "capacity": e.capacity,
        "seats_taken": seats_taken,
        "poster_url": e.poster_url,
        "verification_label": e.verification_label,
        "organizer_name": e.organizer.org_name if e.organizer else None,
        "distance_km": None if r.distance_km is None else round(r.distance_km, 1),
        "travel_min": r.travel_min,
        "fits": r.passed,
        "almost": ev.almost,
        "clash": r.reason if (r.almost or (r.passed and r.window is None)) else None,
        "match": s.match if s else None,
        "interest": s.interest if s else None,
        "reasons": s.texts if s else [],
        "card_reasons": s.card_texts if s else [],
        "waitlist": r.waitlist,
        "saved": saved,
        "dismissed": ev.dismissed,
    }


def event_detail(ev: Evaluated, seats_taken: int, saved: bool, reg: dict | None = None) -> dict:
    e, r = ev.event, ev.result
    out = event_card(ev, seats_taken, saved, reg)
    org = e.organizer
    out.update({
        "description": e.description,
        "address": e.address,
        "lat": e.lat,
        "lng": e.lng,
        "registration_deadline": iso_utc(e.registration_deadline),
        "registration_url": e.registration_url,
        "eligibility_text": (e.eligibility or {}).get("text") or None,
        "skill_level": e.skill_level,
        "status": e.status,
        "organizer": {"name": org.org_name, "trust_level": org.trust_level, "trust_label": TRUST_LABELS.get(org.trust_level)} if org else None,
        "why_not": None if r.passed or r.almost else r.reason,
        "maps_url": f"https://www.google.com/maps/dir/?api=1&destination={e.lat},{e.lng}" if e.lat is not None and e.lng is not None else None,
    })
    return out
