"""Semester recap (feature 4): everything the story slides need, in one response.

Built from the same attended list as the Record (only organizer check-ins), limited to a half year:
H1 = January to June, H2 = July to December. First name only; never the email.
"""

import re
from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, User
from . import feedcache
from .record import Attended, attended, streaks

PERIOD = re.compile(r"^(\d{4})-H([12])$")
THRESHOLD = 0.6


def parse_period(period: str) -> tuple[date, date, str]:
    m = PERIOD.match(period or "")
    if not m:
        raise ValueError("Use a period like 2026-H2.")
    year, half = int(m.group(1)), int(m.group(2))
    if half == 1:
        return date(year, 1, 1), date(year, 6, 30), f"Jan to Jun {year}"
    return date(year, 7, 1), date(year, 12, 31), f"Jul to Dec {year}"


def style_for(items: list[Attended], category_counts: Counter) -> dict:
    """A light label from real data (not a personality test). First rule that applies wins, in this order."""
    n = len(items)
    if n == 0:
        return {"label": "Rising Regular", "line": "Every semester starts somewhere.", "reason": "No events yet this period."}
    weekend = sum(1 for a in items if a.local_start.weekday() >= 5)
    night = sum(1 for a in items if a.local_start.hour >= 18)
    early = sum(1 for a in items if a.local_start.hour < 10)
    top_slug, top_n = category_counts.most_common(1)[0] if category_counts else (None, 0)
    if weekend / n >= THRESHOLD:
        return {"label": "Weekend Explorer", "line": "Your Saturdays and Sundays were busy in the best way.",
                "reason": f"{weekend} of your {n} events were on weekends."}
    if night / n >= THRESHOLD:
        return {"label": "Night Owl", "line": "You come alive after sunset.", "reason": f"{night} of your {n} events started after 6 PM."}
    if early / n >= THRESHOLD:
        return {"label": "Early Bird", "line": "First in, best seat.", "reason": f"{early} of your {n} events started before 10 AM."}
    if top_slug and top_n / n >= THRESHOLD:
        return {"label": "Deep Diver", "line": "You went deep on one thing.", "reason": f"{top_n} of your {n} events were in one topic."}
    if len(category_counts) >= 4:
        return {"label": "Curious Mind", "line": "You kept trying new things.", "reason": f"You tried {len(category_counts)} different topics."}
    return {"label": "Rising Regular", "line": "You keep showing up. That's the whole trick.", "reason": f"{n} events and counting."}


def build_recap(db: Session, user: User, period: str) -> dict:
    key = f"recap:{period}"
    cached = feedcache.get(user.id, key, ttl=60)
    if cached is not None:
        return cached
    start, end, label = parse_period(period)
    items = attended(db, user, start, end)
    n = len(items)
    cats = {c.slug: c for c in db.scalars(select(Category))}
    counts = Counter(a.event.category_slug for a in items if a.event.category_slug)
    categories = [{"slug": s, "name": cats[s].name if s in cats else s, "emoji": cats[s].emoji if s in cats else "", "count": c}
                  for s, c in counts.most_common()]
    months = Counter(a.local_start.strftime("%B") for a in items)
    busiest = months.most_common(1)[0] if months else None
    _, longest = streaks(items)
    pct = lambda k: round(100 * k / n) if n else 0  # noqa: E731
    result = {
        "period": period,
        "period_label": label,
        "first_name": (user.name or "").split(" ")[0],
        "college": user.college,  # shown on the image only if the student turns it on
        "events_attended": n,
        "hours": round(sum(a.hours for a in items), 1),
        "categories": categories,
        "top_categories": categories[:3],
        "topics": len(categories),
        "longest_streak_weeks": longest,
        "busiest_month": {"month": busiest[0], "count": busiest[1]} if busiest else None,
        "weekend_pct": pct(sum(1 for a in items if a.local_start.weekday() >= 5)),
        "evening_pct": pct(sum(1 for a in items if a.local_start.hour >= 18)),
        "morning_pct": pct(sum(1 for a in items if a.local_start.hour < 10)),
        "style": style_for(items, counts),
        "short": n < 3,
    }
    feedcache.put(user.id, result, key)
    return result
