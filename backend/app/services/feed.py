"""Runs the hard filters and ranking for one user over all open events (cached 30 s per user)."""

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AvailabilitySlot, Event, Feedback, Registration, User
from ..timeutil import ist_today, utcnow
from . import feedcache
from .matching import FilterResult, check_event
from .ranking import ALMOST_MIN_INTEREST, Scored, build_profile, score_event
from .scheduling import free_windows

HORIZON_DAYS = 60
SEAT_STATUSES = ("registered", "promoted_pending", "attended")


@dataclass
class Evaluated:
    event: Event
    result: FilterResult
    scored: Scored | None  # set for events that pass, and for schedule-only misses
    dismissed: bool

    @property
    def for_you(self) -> bool:
        return self.result.passed and not self.dismissed

    @property
    def almost(self) -> bool:
        return (
            self.result.almost
            and not self.dismissed
            and self.scored is not None
            and self.scored.interest >= ALMOST_MIN_INTEREST
        )


@dataclass
class FeedData:
    items: list[Evaluated]
    counts: dict[str, int]  # event_id -> seats taken

    def for_you(self) -> list[Evaluated]:
        return sorted((i for i in self.items if i.for_you), key=lambda i: (-i.scored.match, i.event.start_at))

    def almost(self) -> list[Evaluated]:
        return sorted((i for i in self.items if i.almost), key=lambda i: (-i.scored.interest, i.event.start_at))


def registered_counts(db: Session, event_ids: list[str] | None = None) -> dict[str, int]:
    q = select(Registration.event_id, func.count()).where(Registration.status.in_(SEAT_STATUSES))
    if event_ids is not None:
        q = q.where(Registration.event_id.in_(event_ids))
    return dict(db.execute(q.group_by(Registration.event_id)).all())


def user_windows(db: Session, user: User):
    slots = db.scalars(select(AvailabilitySlot).where(AvailabilitySlot.user_id == user.id)).all()
    today = ist_today()
    return free_windows(slots, today - timedelta(days=1), today + timedelta(days=HORIZON_DAYS))


def user_profile(db: Session, user: User):
    """Interest vector plus the tags of events the user marked "not for me"."""
    rows = db.execute(
        select(Feedback.event_id, Event.tags)
        .join(Event, Event.id == Feedback.event_id)
        .where(Feedback.user_id == user.id, Feedback.kind == "not_for_me")
    ).all()
    tags = Counter(t for _, ts in rows for t in (ts or []))
    return build_profile(user, tags), {eid for eid, _ in rows}


def evaluate_one(db: Session, user: User, event: Event, windows=None, profile=None, dismissed=None, count=None) -> Evaluated:
    windows = user_windows(db, user) if windows is None else windows
    if profile is None or dismissed is None:
        profile, dismissed = user_profile(db, user)
    if count is None:
        count = registered_counts(db, [event.id]).get(event.id, 0)
    fr = check_event(user, event, windows, utcnow(), count)
    scored = score_event(event, user, fr, profile) if (fr.passed or fr.almost) else None
    return Evaluated(event, fr, scored, event.id in dismissed)


def evaluate(db: Session, user: User) -> FeedData:
    cached = feedcache.get(user.id)
    if cached is not None:
        return cached
    now = utcnow()
    events = db.scalars(
        select(Event).where(Event.status == "published", Event.start_at > now).order_by(Event.start_at)
    ).unique().all()
    counts = registered_counts(db)
    windows = user_windows(db, user)
    profile, dismissed = user_profile(db, user)
    items = [evaluate_one(db, user, e, windows, profile, dismissed, counts.get(e.id, 0)) for e in events]
    data = FeedData(items, counts)
    feedcache.put(user.id, data)
    return data
