"""Participation record (feature 3), and the numbers the semester recap (feature 4) is built from.

Only organizer-confirmed check-ins count (registration status "attended"). Private to the student.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Registration, User
from ..timeutil import ist_today, iso_utc, to_ist


@dataclass
class Attended:
    event: Event
    checked_in_at: datetime | None

    @property
    def hours(self) -> float:
        if not self.event.start_at or not self.event.end_at or self.event.event_type == "internship":
            return 0.0
        return max(0.0, (self.event.end_at - self.event.start_at).total_seconds() / 3600)

    @property
    def local_start(self) -> datetime:
        return to_ist(self.event.start_at)


def attended(db: Session, user: User, start: date | None = None, end: date | None = None) -> list[Attended]:
    rows = db.execute(
        select(Event, Registration.checked_in_at).join(Registration, Registration.event_id == Event.id)
        .where(Registration.user_id == user.id, Registration.status == "attended")
        .order_by(Event.start_at.desc())
    ).unique().all()
    out = [Attended(e, c) for e, c in rows if e.start_at]
    if start:
        out = [a for a in out if a.local_start.date() >= start]
    if end:
        out = [a for a in out if a.local_start.date() <= end]
    return out


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def streaks(items: list[Attended], today: date | None = None) -> tuple[int, int]:
    """(current, longest) streak in calendar weeks (Mon to Sun) with at least one attended event.

    The current week only counts once it has an event, and never breaks the streak before it ends.
    """
    today = today or ist_today()
    weeks = {monday(a.local_start.date()) for a in items}
    if not weeks:
        return 0, 0
    this_week = monday(today)
    w = this_week if this_week in weeks else this_week - timedelta(weeks=1)
    current = 0
    while w in weeks:
        current += 1
        w -= timedelta(weeks=1)
    longest, run, prev = 0, 0, None
    for w in sorted(weeks):
        run = run + 1 if prev is not None and w - prev == timedelta(weeks=1) else 1
        longest, prev = max(longest, run), w
    return current, longest


def record_out(db: Session, user: User) -> dict:
    items = attended(db, user)
    current, longest = streaks(items)
    return {
        "events_attended": len(items),
        "hours": round(sum(a.hours for a in items), 1),
        "current_streak_weeks": current,
        "longest_streak_weeks": longest,
        "events": [{
            "event_id": a.event.id, "title": a.event.title, "start_at": iso_utc(a.event.start_at), "end_at": iso_utc(a.event.end_at),
            "organizer_name": a.event.organizer.org_name if a.event.organizer else None,
            "category_slug": a.event.category_slug, "event_type": a.event.event_type,
            "checked_in_at": iso_utc(a.checked_in_at),
        } for a in items],
    }
