"""Runs the hard filters for one user over all open events."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AvailabilitySlot, Event, Registration, User
from ..timeutil import ist_today, utcnow
from . import feedcache
from .matching import FilterResult, check_event
from .scheduling import free_windows

HORIZON_DAYS = 60


@dataclass
class Evaluated:
    event: Event
    result: FilterResult


def registered_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Registration.event_id, func.count())
        .where(Registration.status.in_(("registered", "promoted_pending", "attended")))
        .group_by(Registration.event_id)
    )
    return dict(rows.all())


def user_windows(db: Session, user: User):
    slots = db.scalars(select(AvailabilitySlot).where(AvailabilitySlot.user_id == user.id)).all()
    today = ist_today()
    return free_windows(slots, today - timedelta(days=1), today + timedelta(days=HORIZON_DAYS))


def evaluate(db: Session, user: User) -> list[Evaluated]:
    cached = feedcache.get(user.id)
    if cached is not None:
        return cached
    now = utcnow()
    events = db.scalars(
        select(Event).where(Event.status == "published", Event.start_at > now).order_by(Event.start_at)
    ).unique().all()
    counts = registered_counts(db)
    windows = user_windows(db, user)
    out = [Evaluated(e, check_event(user, e, windows, now, counts.get(e.id, 0))) for e in events]
    feedcache.put(user.id, out)
    return out
