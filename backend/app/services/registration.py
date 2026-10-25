"""Registration, cancellation and waitlist promotion (SPEC 5.9), plus per-registration facts.

Seat changes for one event run under a per-event lock and in one transaction, so two cancels
racing each other free two seats and promote exactly two people, never the same seat twice.
"""

import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, Registration, User
from ..timeutil import iso_utc, utcnow
from . import feedcache
from .showup_score import Likelihood, leave_by, likelihood
from .travel import haversine_km, travel_minutes, user_home

SEAT = ("registered", "promoted_pending", "attended")
ACTIVE = SEAT + ("waitlisted",)

_guard = threading.Lock()
_event_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


@contextmanager
def event_lock(event_id: str):
    with _guard:
        lock = _event_locks[event_id]
    with lock:
        yield


def seats_taken(db: Session, event_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event_id, Registration.status.in_(SEAT))) or 0


def active_registration(db: Session, user_id: str, event_id: str) -> Registration | None:
    return db.scalar(select(Registration).where(Registration.user_id == user_id, Registration.event_id == event_id, Registration.status.in_(ACTIVE)))


def travel_for(user: User, event: Event) -> tuple[float | None, int]:
    if event.mode != "in_person" or event.lat is None or event.lng is None:
        return None, 0
    d = haversine_km(*user_home(user), event.lat, event.lng)
    return d, travel_minutes(d)


def leave_by_for(user: User, event: Event) -> datetime | None:
    distance, travel = travel_for(user, event)
    return None if distance is None else leave_by(event.start_at, travel)


def past_attendance(db: Session, user_id: str) -> float | None:
    rows = dict(db.execute(
        select(Registration.status, func.count()).where(Registration.user_id == user_id, Registration.status.in_(("attended", "no_show")))
        .group_by(Registration.status)
    ).all())
    total = rows.get("attended", 0) + rows.get("no_show", 0)
    return rows.get("attended", 0) / total if total >= 2 else None


def compute_likelihood(db: Session, user: User, event: Event, reg: Registration) -> Likelihood:
    from .feed import evaluate_one

    ev = evaluate_one(db, user, event)
    distance, _ = travel_for(user, event)
    days_before = (event.start_at - reg.registered_at).total_seconds() / 86400
    with_friend = bool(reg.group_id) and db.scalar(
        select(func.count()).select_from(Registration).where(
            Registration.group_id == reg.group_id, Registration.id != reg.id, Registration.status.in_(ACTIVE))
    ) > 0
    return likelihood(
        interest=ev.scored.interest if ev.scored else None,
        distance_km=distance,
        days_before=days_before,
        reminder_confirmed=reg.reminder_confirmed,
        past_rate=past_attendance(db, user.id),
        slack_min=ev.scored.slack_min if ev.scored else None,
        with_friend=with_friend,
    )


def _renumber(db: Session, event_id: str) -> None:
    waiting = db.scalars(
        select(Registration).where(Registration.event_id == event_id, Registration.status == "waitlisted")
        .order_by(Registration.waitlist_position, Registration.registered_at)
    ).all()
    for i, r in enumerate(waiting, start=1):
        r.waitlist_position = i


def _promote(db: Session, event: Event, now: datetime) -> list[Registration]:
    """Offer every free seat to the next people in line. Caller holds the event lock."""
    if event.capacity is None:
        return []
    db.flush()
    free = event.capacity - seats_taken(db, event.id)
    promoted = []
    while free > 0:
        nxt = db.scalar(
            select(Registration).where(Registration.event_id == event.id, Registration.status == "waitlisted")
            .order_by(Registration.waitlist_position, Registration.registered_at).limit(1)
        )
        if nxt is None:
            break
        nxt.status = "promoted_pending"
        nxt.waitlist_position = None
        nxt.promotion_expires_at = now + timedelta(minutes=settings.effective_waitlist_minutes)
        db.flush()
        promoted.append(nxt)
        free -= 1
    _renumber(db, event.id)
    return promoted


def _check_open(event: Event, now: datetime) -> None:
    if event.status != "published":
        raise HTTPException(409, "This event isn't open for registration.")
    if event.start_at is None or event.start_at <= now:
        raise HTTPException(409, "This event has already started.")
    if event.registration_deadline is not None and event.registration_deadline <= now:
        raise HTTPException(409, "Registration for this event has closed.")


def register(db: Session, user: User, event: Event, external: bool = False, now: datetime | None = None) -> Registration:
    now = now or utcnow()
    with event_lock(event.id):
        existing = active_registration(db, user.id, event.id)
        if existing:
            return existing
        _check_open(event, now)
        reg = Registration(user_id=user.id, event_id=event.id, registered_at=now, external=external)
        if not external and event.capacity is not None and seats_taken(db, event.id) >= event.capacity:
            last = db.scalar(select(func.max(Registration.waitlist_position)).where(Registration.event_id == event.id, Registration.status == "waitlisted"))
            reg.status, reg.waitlist_position = "waitlisted", (last or 0) + 1
        else:
            reg.status = "registered"
        db.add(reg)
        db.flush()
        reg.showup_likelihood = compute_likelihood(db, user, event, reg).p
        db.commit()
    feedcache.invalidate_all()  # seat counts changed for everyone
    return reg


def cancel(db: Session, reg: Registration, now: datetime | None = None) -> list[Registration]:
    """Can't make it: free the seat and offer it to the waitlist. Returns who was promoted."""
    now = now or utcnow()
    with event_lock(reg.event_id):
        db.refresh(reg)
        if reg.status not in ACTIVE or reg.status == "attended":
            raise HTTPException(409, "This registration is no longer active.")
        held_seat = reg.status in ("registered", "promoted_pending")
        reg.status, reg.cancelled_at, reg.waitlist_position, reg.promotion_expires_at = "cancelled", now, None, None
        event = db.get(Event, reg.event_id)
        promoted = _promote(db, event, now) if held_seat else []
        _renumber(db, event.id)
        db.commit()
    feedcache.invalidate_all()
    return promoted


def confirm_seat(db: Session, reg: Registration, now: datetime | None = None) -> Registration:
    now = now or utcnow()
    with event_lock(reg.event_id):
        db.refresh(reg)
        if reg.status == "registered":
            return reg
        if reg.status != "promoted_pending":
            raise HTTPException(409, "There's no seat waiting for you on this event.")
        if reg.promotion_expires_at is None or reg.promotion_expires_at <= now:
            raise HTTPException(409, "Sorry, the time to confirm ran out and the seat went to the next person.")
        reg.status, reg.promotion_expires_at = "registered", None
        db.commit()
    feedcache.invalidate_all()
    return reg


def expire_offers(db: Session, now: datetime | None = None) -> list[Registration]:
    """Seat offers nobody confirmed in time pass to the next person in line."""
    now = now or utcnow()
    expired = db.scalars(select(Registration).where(Registration.status == "promoted_pending", Registration.promotion_expires_at <= now)).all()
    promoted: list[Registration] = []
    for event_id in {r.event_id for r in expired}:
        with event_lock(event_id):
            for r in db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.status == "promoted_pending",
                                                          Registration.promotion_expires_at <= now)).all():
                r.status, r.cancelled_at, r.promotion_expires_at = "cancelled", now, None
            promoted += _promote(db, db.get(Event, event_id), now)
            db.commit()
    if expired:
        feedcache.invalidate_all()
    return promoted


def registration_out(db: Session, reg: Registration, user: User) -> dict:
    from .together import companions_out  # together builds on this module

    e = db.get(Event, reg.event_id)
    lb = leave_by_for(user, e) if e.start_at else None
    return {
        "companions": companions_out(db, reg),
        "id": reg.id,
        "status": reg.status,
        "waitlist_position": reg.waitlist_position,
        "promotion_expires_at": iso_utc(reg.promotion_expires_at),
        "checkin_token": reg.checkin_token,
        "checkin_code": reg.checkin_code,
        "checked_in_at": iso_utc(reg.checked_in_at),
        "reminder_confirmed": reg.reminder_confirmed,
        "external": reg.external,
        "leave_by": iso_utc(lb),
        "registered_at": iso_utc(reg.registered_at),
        "event": {
            "id": e.id, "title": e.title, "category": e.category, "poster_url": e.poster_url, "mode": e.mode,
            "venue_name": e.venue_name, "address": e.address, "start_at": iso_utc(e.start_at), "end_at": iso_utc(e.end_at),
            "fee_inr": e.fee_inr, "status": e.status,
            "maps_url": f"https://www.google.com/maps/dir/?api=1&destination={e.lat},{e.lng}" if e.lat is not None else None,
        },
    }
