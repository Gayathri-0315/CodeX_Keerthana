"""Explore: every upcoming, published event (prompt v2, item 3), filtered and sorted by start date.

Spam-blocked, pending-review, cancelled and draft events never appear: only `published` events are
loaded. Nothing is hidden for not fitting the student's free time; each item carries a time-fit badge.
Natural-language search (item 19) feeds its parsed filters into the same `apply_filters`.
"""

from dataclasses import dataclass, field
from datetime import date

from .feed import Evaluated, FeedData
from .matching import time_fit
from ..timeutil import to_ist


@dataclass
class Filters:
    category: str | None = None  # category slug (see services/categories.py)
    date_from: date | None = None  # IST dates, inclusive
    date_to: date | None = None
    price: str | None = None  # free | paid
    mode: str | None = None  # online | in_person (hybrid counts as both)
    q: str | None = None  # title search
    max_fee_inr: int | None = None
    tags: list[str] = field(default_factory=list)
    event_type: str | None = None
    organizer_ids: set[str] | None = None  # "Following": only clubs the student follows
    # From natural-language search:
    categories: list[str] = field(default_factory=list)  # any of these
    time_of_day: str | None = None  # morning | afternoon | evening | night (IST start time)
    keywords: list[str] = field(default_factory=list)  # any word in the title, tags or description
    max_distance_km: int | None = None  # only applied when we know the student's distance


HOURS = {"morning": (5, 12), "afternoon": (12, 17), "evening": (16, 21), "night": (19, 28)}


def _matches(ev: Evaluated, f: Filters) -> bool:
    e = ev.event
    if f.organizer_ids is not None and e.organizer_id not in f.organizer_ids:
        return False
    if f.event_type and e.event_type != f.event_type:
        return False
    if f.category and e.category_slug != f.category:
        return False
    if f.categories and e.category_slug not in f.categories:
        return False
    start = to_ist(e.start_at)
    if f.time_of_day in HOURS:
        lo, hi = HOURS[f.time_of_day]
        hour = start.hour + (24 if start.hour < 4 else 0)
        if not lo <= hour < hi:
            return False
    if f.keywords:
        text = " ".join([e.title, e.description or "", " ".join(e.tags or [])]).lower()
        if not any(k in text for k in f.keywords):
            return False
    if f.max_distance_km is not None and e.mode != "online":
        km = getattr(ev.result, "distance_km", None)
        if km is not None and km > f.max_distance_km:
            return False
    d = start.date()
    if f.date_from and d < f.date_from:
        return False
    if f.date_to and d > f.date_to:
        return False
    if f.price == "free" and e.fee_inr != 0:
        return False
    if f.price == "paid" and e.fee_inr == 0:
        return False
    if f.max_fee_inr is not None and e.fee_inr > f.max_fee_inr:
        return False
    if f.mode == "online" and e.mode == "in_person":
        return False
    if f.mode == "in_person" and e.mode == "online":
        return False
    if f.q and f.q.strip().lower() not in e.title.lower():
        return False
    if f.tags and not set(f.tags) & set(e.tags or []):
        return False
    return True


def apply_filters(data: FeedData, f: Filters) -> list[Evaluated]:
    return sorted((i for i in data.items if _matches(i, f)), key=lambda i: i.event.start_at)


def fit_badge(ev: Evaluated, user, windows, going=()) -> dict | None:
    if ev.event.event_type == "internship":
        return None  # no session to fit; cards show "Apply by <date>" instead
    r = ev.result
    if r.passed and r.window is not None:
        return {"fits": True, "reason": None}
    if r.failed_rule == "schedule" or (r.passed and r.window is None):
        return {"fits": False, "reason": r.reason}
    fits, reason = time_fit(user, ev.event, windows, going)
    return {"fits": fits, "reason": reason}
