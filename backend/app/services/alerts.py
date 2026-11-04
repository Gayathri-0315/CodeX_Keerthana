"""Saved alerts ("Remind me of similar events", prompt v2 item 2).

An alert keeps the Almost event's main tags and the day/time window it clashed with. When a new
event is published, each student with a matching alert is notified if the event:
  - shares at least one of the alert's tags,
  - falls on the same weekday and overlaps the saved time window, and
  - passes that student's normal hard filters (strict schedule, distance, budget, eligibility...).
Delivery uses the same weekly cap, quiet hours, pause and dedupe as match alerts. No match, no alert.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, SavedAlert, User
from ..timeutil import DAY_NAMES, fmt_time, iso_utc, to_ist, utcnow

MAX_TAGS = 3
MAX_ALERTS = 20


def window_of(event: Event) -> tuple[int, int, int]:
    """(weekday, start_min, end_min) in IST. An event past midnight is clipped to the end of its start day."""
    start, end = to_ist(event.start_at), to_ist(event.end_at)
    end_min = end.hour * 60 + end.minute if end.date() == start.date() else 1440
    return start.weekday(), start.hour * 60 + start.minute, max(end_min, start.hour * 60 + start.minute + 1)


def create_from_event(db: Session, user: User, event: Event) -> SavedAlert:
    from fastapi import HTTPException

    existing = db.scalar(select(SavedAlert).where(SavedAlert.user_id == user.id, SavedAlert.source_event_id == event.id))
    if existing:
        return existing
    if len(db.scalars(select(SavedAlert.id).where(SavedAlert.user_id == user.id)).all()) >= MAX_ALERTS:
        raise HTTPException(409, f"You have {MAX_ALERTS} saved alerts. Delete one in Settings first.")
    tags = list(dict.fromkeys(event.tags or []))[:MAX_TAGS] or ([event.category.lower()] if event.category else [])
    dow, s, e = window_of(event)
    alert = SavedAlert(user_id=user.id, source_event_id=event.id, source_title=event.title, tags=tags,
                       day_of_week=dow, start_min=s, end_min=e)
    db.add(alert)
    db.commit()
    return alert


def matches(alert: SavedAlert, event: Event) -> bool:
    if event.id == alert.source_event_id or not event.start_at or not event.end_at:
        return False
    tags = set(event.tags or []) | ({event.category.lower()} if event.category else set())
    if not tags & set(alert.tags or []):
        return False
    dow, s, e = window_of(event)
    return dow == alert.day_of_week and s < alert.end_min and e > alert.start_min


def window_text(alert: SavedAlert) -> str:
    from datetime import datetime

    def t(m: int) -> str:
        return "midnight" if m >= 1440 else fmt_time(datetime(2000, 1, 1, m // 60, m % 60))

    return f"{DAY_NAMES[alert.day_of_week]}s, {t(alert.start_min)} to {t(alert.end_min)}"


def alert_out(a: SavedAlert) -> dict:
    return {"id": a.id, "tags": a.tags, "source_title": a.source_title, "source_event_id": a.source_event_id,
            "window": window_text(a), "day_of_week": a.day_of_week, "start_min": a.start_min, "end_min": a.end_min,
            "created_at": iso_utc(a.created_at)}


def suggest_similar(db: Session, event: Event, now=None, bypass_quiet: bool = False) -> int:
    """Notify students whose saved alert matches this newly published event. Returns how many were told."""
    from . import notify
    from .feed import evaluate_one

    now = now or utcnow()
    if event.status != "published" or event.verification_label == "unverified" or event.risk_score >= 30:
        return 0
    sent = 0
    seen: set[str] = set()
    for alert in db.scalars(select(SavedAlert).order_by(SavedAlert.created_at)).all():
        if alert.user_id in seen or not matches(alert, event):
            continue
        seen.add(alert.user_id)
        user = db.get(User, alert.user_id)
        if user is None or user.role != "student" or notify.is_paused(user, now) or not notify.any_channel(user):
            continue
        if notify.already_sent(db, user, event.id, "similar") or notify.already_sent(db, user, event.id, "match"):
            continue
        ev = evaluate_one(db, user if user.strict_schedule else notify._strict(user), event)
        if not ev.result.passed or ev.dismissed:
            continue
        if not notify.cap_allows(db, user, "similar", now):
            continue
        title, body = notify.similar_copy(event, alert.source_title)
        if notify.create(db, user, "similar", event, title, body, {"alert_id": alert.id}, bypass_quiet=bypass_quiet, now=now):
            sent += 1
    return sent
