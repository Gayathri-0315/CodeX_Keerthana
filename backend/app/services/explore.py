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


def _matches(ev: Evaluated, f: Filters) -> bool:
    e = ev.event
    if f.event_type and e.event_type != f.event_type:
        return False
    if f.category and e.category_slug != f.category:
        return False
    d = to_ist(e.start_at).date()
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
