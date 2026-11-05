"""'Your week' (feature 1): one response with each day's free windows, busy time, events the student is
going to, and the events that fit (the two best shown as chips, the rest listed when a day is opened).

Built from the cached feed evaluation, so it costs one slot query and one registration query on top.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AvailabilitySlot, Event, Registration, User
from ..timeutil import to_ist
from . import feedcache
from .feed import evaluate
from .scheduling import day_intervals, merge, subtract

DAY_START, DAY_END = 6 * 60, 22 * 60  # the waking hours shown in each lane
CHIPS_PER_DAY = 2


def _minutes(dt: datetime, day: date) -> int:
    local = to_ist(dt)
    if local.date() < day:
        return 0
    if local.date() > day:
        return 1440
    return local.hour * 60 + local.minute


def _clip(spans: list[tuple[int, int]]) -> list[dict]:
    out = []
    for s, e in spans:
        s, e = max(s, DAY_START), min(e, DAY_END)
        if e > s:
            out.append({"start_min": s, "end_min": e})
    return out


def _brief(e: Event, day: date, **extra) -> dict:
    return {"event_id": e.id, "title": e.title, "start_min": _minutes(e.start_at, day), "end_min": _minutes(e.end_at, day),
            "category_slug": e.category_slug, "event_type": e.event_type, **extra}


def build_week(db: Session, user: User, start: date) -> dict:
    key = f"week:{start.isoformat()}"
    cached = feedcache.get(user.id, key)
    if cached is not None:
        return cached

    days = [start + timedelta(days=i) for i in range(7)]
    slots = db.scalars(select(AvailabilitySlot).where(AvailabilitySlot.user_id == user.id)).all()
    data = evaluate(db, user)

    mine = db.execute(
        select(Registration.status, Event).join(Event, Event.id == Registration.event_id)
        .where(Registration.user_id == user.id, Registration.status.in_(("registered", "waitlisted", "promoted_pending")),
               Event.status == "published", Event.event_type != "internship")
    ).unique().all()
    going_ids = {e.id for _, e in mine}

    # Events that truly fit the free time (a free window was found), best match first.
    fitting = [i for i in data.for_you() if i.result.window is not None and i.event.event_type != "internship"
               and i.event.id not in going_ids]

    out_days = []
    any_free = False
    for d in days:
        free = day_intervals(slots, d)
        any_free = any_free or bool(free)
        busy = subtract([(DAY_START, DAY_END)], merge(free))
        going = [_brief(e, d, kind="going" if status == "registered" else "waitlist")
                 for status, e in mine if e.start_at and to_ist(e.start_at).date() == d]
        fits = [_brief(i.event, d, match=i.scored.match if i.scored else None, fee_inr=i.event.fee_inr,
                       organizer_name=i.event.organizer.org_name if i.event.organizer else None)
                for i in fitting if to_ist(i.event.start_at).date() == d]
        out_days.append({
            "date": d.isoformat(),
            "free": _clip(free),
            "busy": _clip(busy),
            "going": sorted(going, key=lambda g: g["start_min"]),
            "recommended": fits[:CHIPS_PER_DAY],
            "fits": fits,
        })
    result = {"start": start.isoformat(), "day_start_min": DAY_START, "day_end_min": DAY_END,
              "has_free_time": any_free, "fits_total": sum(len(d["fits"]) for d in out_days), "days": out_days}
    feedcache.put(user.id, result, key)
    return result
