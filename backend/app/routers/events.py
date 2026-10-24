from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..seed.venues import AREAS
from ..services.feed import evaluate
from ..timeutil import iso_utc

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Upcoming published events, each marked with whether it fits the user."""
    out = []
    for item in evaluate(db, user):
        e, r = item.event, item.result
        out.append({
            "id": e.id,
            "title": e.title,
            "category": e.category,
            "tags": e.tags,
            "mode": e.mode,
            "venue_name": e.venue_name,
            "start_at": iso_utc(e.start_at),
            "end_at": iso_utc(e.end_at),
            "fee_inr": e.fee_inr,
            "verification_label": e.verification_label,
            "organizer_name": e.organizer.org_name if e.organizer else None,
            "fits": r.passed,
            "almost": r.almost,
            "reason": r.reason,
            "distance_km": None if r.distance_km is None else round(r.distance_km, 1),
            "waitlist": r.waitlist,
        })
    return {"events": out}


@router.get("/areas")
def areas(q: str = Query("", max_length=60)):
    q = q.strip().lower()
    return {"areas": [a for a in AREAS if q in a["name"].lower()]}
