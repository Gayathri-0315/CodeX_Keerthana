"""Guest browsing (prompt v2, item 9): upcoming published events without an account.

Only `published` events with a future start are listed, so spam-blocked, pending-review, cancelled and
draft events never appear. Cards carry no personal data and no fit information.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import RateLimit
from ..models import Event
from ..serializers import event_card
from ..services.explore import Filters, apply_filters
from ..services.feed import Evaluated, FeedData, registered_counts
from ..services.matching import FilterResult
from ..timeutil import utcnow

router = APIRouter(prefix="/public", tags=["public"])
public_limit = RateLimit(120, 60, "Too many requests. Wait a moment and try again.")


def guest_data(db: Session) -> FeedData:
    events = db.scalars(
        select(Event).where(Event.status == "published", Event.start_at > utcnow()).order_by(Event.start_at)
    ).unique().all()
    guest = FilterResult(False, "guest")
    return FeedData([Evaluated(e, guest, None, False) for e in events], registered_counts(db))


def guest_card(data: FeedData, ev: Evaluated) -> dict:
    card = event_card(ev, data.counts.get(ev.event.id, 0), False)
    card.update({"fits": None, "guest": True})
    return card


@router.get("/events", dependencies=[Depends(public_limit)])
def public_events(
    category: str | None = Query(None, max_length=60),
    date_from: date | None = None,
    date_to: date | None = None,
    price: Literal["free", "paid"] | None = None,
    mode: Literal["online", "in_person"] | None = None,
    q: str | None = Query(None, max_length=100),
    event_type: Literal["hackathon", "competition", "internship", "workshop", "conference", "meetup", "webinar", "other"] | None = None,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = None,
    db: Session = Depends(get_db),
):
    from .feed import parse_cursor

    data = guest_data(db)
    items = apply_filters(data, Filters(category=category, date_from=date_from, date_to=date_to, price=price, mode=mode, q=q,
                                         event_type=event_type))
    offset = parse_cursor(cursor)
    page = items[offset : offset + limit]
    return {"items": [guest_card(data, i) for i in page],
            "next_cursor": str(offset + limit) if offset + limit < len(items) else None, "total": len(items)}


@router.get("/categories", dependencies=[Depends(public_limit)])
def public_categories(db: Session = Depends(get_db)):
    from ..services.categories import with_counts

    return {"categories": with_counts(db, [i.event for i in guest_data(db).items])}
