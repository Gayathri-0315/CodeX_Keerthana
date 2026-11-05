"""Notifications (SPEC 5.5, 8.9): copy, delivery rules, channels.

Suggestions (match, deadline, seat_opened) obey the weekly cap (urgent types may go one over),
pause, and dedupe. Anything created during quiet hours is stored and delivered when they end,
except a seat offer, which only lasts minutes.
"""

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, Notification, Registration, User
from ..timeutil import DAY_NAMES, fmt_range, fmt_time, iso_utc, to_ist, utcnow
from . import stream
from .email import send_email

log = logging.getLogger("showup.notify")

SUGGESTION = {"match", "similar", "deadline", "seat_opened"}
URGENT = {"seat_opened", "deadline"}
# Sent at once even in quiet hours: a 15-minute seat offer, and confirmations of something the user just did.
ALWAYS_NOW = {"seat_opened", "registered", "waitlisted"}
MIN_MATCH = 75

# Which alerts also go out by email (when the user has email on). Each gets one line and one button.
EMAIL_TYPES = {"match", "similar", "deadline", "registered", "waitlisted", "seat_opened", "reminder_24h",
               "reminder_leave_by", "cancelled_event", "message", "new_message",
               "org_registration", "org_cancellation", "org_waitlist", "org_review", "org_reminder", "org_digest", "how_was"}
# While alerts are paused, only these still email: things the user is actively waiting on.
PAUSE_EXEMPT = {"seat_opened", "cancelled_event", "registered", "waitlisted", "new_message", "org_review"}
# Shown as a live toast? Registration confirmations already show their own animation and toast in the app.
NO_TOAST = {"registered", "waitlisted"}


# ---- rules ----

def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_quiet_hours(user: User, now: datetime) -> bool:
    t = to_ist(now).time()
    start, end = _hhmm(user.quiet_hours_start), _hhmm(user.quiet_hours_end)
    if start == end:
        return False
    return start <= t < end if start < end else (t >= start or t < end)


def is_paused(user: User, now: datetime) -> bool:
    return user.notif_paused_until is not None and user.notif_paused_until > now


def weekly_suggestions(db: Session, user: User, now: datetime) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id,
            Notification.type.in_(SUGGESTION),
            Notification.created_at > now - timedelta(days=7),
        )
    ) or 0


def cap_allows(db: Session, user: User, kind: str, now: datetime) -> bool:
    used = weekly_suggestions(db, user, now)
    return used < user.notif_max_per_week or (kind in URGENT and used < user.notif_max_per_week + 1)


def any_channel(user: User) -> bool:
    ch = user.notif_channels or {}
    return bool(ch.get("in_app") or ch.get("email"))


def already_sent(db: Session, user: User, event_id: str | None, kind: str) -> bool:
    return db.scalar(
        select(Notification.id).where(Notification.user_id == user.id, Notification.event_id == event_id, Notification.type == kind).limit(1)
    ) is not None


# ---- copy (SPEC 8.9 copy bank; bodies under 90 characters) ----

def _short(title: str, n: int = 38) -> str:
    return title if len(title) <= n else title[: n - 1].rstrip() + "…"


def _fit(s: str) -> str:
    return s if len(s) <= 90 else s[:89].rstrip() + "…"


def match_copy(event: Event, distance_km: float | None) -> tuple[str, str]:
    start, end = to_ist(event.start_at), to_ist(event.end_at)
    day = DAY_NAMES[start.weekday()]
    if event.fee_inr == 0:
        return "Free and on your way", _fit(f"{_short(event.title)}, {day[:3]} {fmt_time(start)}. Matches your interests.")
    where = "Online" if distance_km is None else f"{max(1, round(distance_km))} km away"
    return f"A seat that fits your {day}", _fit(f"{_short(event.title)}, {fmt_range(start, end)}. {where}, ₹{event.fee_inr}.")


def similar_copy(event: Event, source_title: str) -> tuple[str, str]:
    start = to_ist(event.start_at)
    return "Something like the one you missed", _fit(
        f"{_short(event.title)}, {DAY_NAMES[start.weekday()][:3]} {fmt_time(start)}. Like {_short(source_title, 30)}.")


def deadline_copy(event: Event, now: datetime) -> tuple[str, str]:
    hours = max(1, round((event.registration_deadline - now).total_seconds() / 3600))
    left = f"{hours} hour{'s' if hours != 1 else ''}" if hours < 48 else "2 days"
    return "Last call", _fit(f"Registration for {_short(event.title)} closes in {left}.")


def seat_copy(event: Event, minutes: int) -> tuple[str, str]:
    return "A seat just opened up", _fit(f"{_short(event.title)} is yours for {minutes} min. Confirm now.")


def reminder_copy(kind: str, event: Event, leave_at: datetime | None, friends: list[str] | None = None) -> tuple[str, str]:
    """`friends`: first names of people going together with this user (shortest copy wins the 90 chars)."""
    start = to_ist(event.start_at)
    where = event.venue_name or "online"
    who = (friends[0] if len(friends) == 1 else f"{friends[0]} +{len(friends) - 1}") if friends else None
    if kind == "reminder_24h":
        tomorrow = (start.date() - to_ist(utcnow()).date()).days == 1
        title = f"Tomorrow, {fmt_time(start)}" if tomorrow else f"{DAY_NAMES[start.weekday()]}, {fmt_time(start)}"
        if who:
            return title, _fit(f"{_short(event.title, 30)} with {who}. Still going?")
        return title, _fit(f"{_short(event.title)} at {where}. Still going?")
    if kind == "reminder_2h":
        return "In 2 hours", _fit(f"{_short(event.title)} at {where} starts at {fmt_time(start)}.")
    if who:
        return "Time to head out", _fit(f"Leave by {fmt_time(to_ist(leave_at))} for {_short(event.title, 26)}. {who} is going too.")
    return "Time to head out", _fit(f"Leave by {fmt_time(to_ist(leave_at))} to reach {_short(event.title, 30)} on time.")


# ---- delivery ----

def actions_for(n: Notification) -> list[dict]:
    p = n.payload or {}
    eid, rid = n.event_id, p.get("registration_id")
    view = {"label": "View", "kind": "view", "event_id": eid}
    if n.type in ("match", "similar", "deadline"):
        return [{"label": "Register", "kind": "register", "event_id": eid}, view]
    if n.type == "seat_opened":
        return [{"label": "Confirm seat", "kind": "confirm_seat", "registration_id": rid}, view]
    if n.type == "reminder_24h":
        return [{"label": "Yes", "kind": "confirm_reminder", "registration_id": rid}, {"label": "Can't make it", "kind": "cancel", "registration_id": rid}]
    if n.type == "reminder_leave_by" and p.get("maps_url"):
        return [{"label": "Directions", "kind": "url", "url": p["maps_url"]}, view]
    if n.type.startswith("org_"):
        return [{"label": "Open event", "kind": "url", "url": f"/organizer/event/{eid}"}] if eid else []
    if n.type == "how_was" and rid:
        return [{"label": "Thumbs up", "kind": "feedback_up", "registration_id": rid},
                {"label": "Thumbs down", "kind": "feedback_down", "registration_id": rid}]
    return [view] if eid else []


def notification_out(n: Notification, event_title: str | None = None) -> dict:
    return {
        "suggested": (n.payload or {}).get("suggested"),
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "event_id": n.event_id,
        "event_title": event_title,
        "actions": actions_for(n),
        "created_at": iso_utc(n.created_at),
        "read_at": iso_utc(n.read_at),
    }


def email_button(n: Notification) -> tuple[str, str]:
    """(label, link) for the one primary button in the email."""
    base = settings.public_url.rstrip("/")
    event = f"{base}/event/{n.event_id}" if n.event_id else base
    p = n.payload or {}
    if n.type == "seat_opened":
        return "Confirm seat", f"{base}/my"
    if n.type in ("match", "similar", "deadline"):
        return "View event", event
    if n.type == "reminder_leave_by" and p.get("maps_url"):
        return "Get directions", p["maps_url"]
    if n.type == "reminder_24h":
        return "I'm still going", f"{base}/my"
    if n.type in ("registered", "waitlisted"):
        return "View my pass" if n.type == "registered" else "View event", f"{base}/my" if n.type == "registered" else event
    if n.type == "new_message":
        return "Read and reply", f"{base}{p.get('path', '/my')}"
    if n.type.startswith("org_"):
        return ("Open event", f"{base}/organizer/event/{n.event_id}") if n.event_id else ("Open dashboard", f"{base}/")
    if n.type == "how_was":
        return "Rate it in one tap", f"{base}/my"
    return "Open ShowUp", event


def wants_email(user: User, n: Notification, now: datetime) -> bool:
    if n.type not in EMAIL_TYPES or not (user.notif_channels or {}).get("email"):
        return False
    return n.type in PAUSE_EXEMPT or not is_paused(user, now)


def deliver(db: Session, n: Notification, user: User, now: datetime | None = None, bypass_quiet: bool = False,
            toast: bool = True) -> bool:
    """Send on every enabled channel, unless it's quiet hours (then a later flush sends it)."""
    now = now or utcnow()
    if n.channel_sent:
        return False
    if not bypass_quiet and n.type not in ALWAYS_NOW and in_quiet_hours(user, now):
        return False
    ch = user.notif_channels or {}
    sent: dict = {}
    if ch.get("in_app") and toast and n.type not in NO_TOAST:
        stream.publish(user.id, "notification", notification_out(n))
        sent["in_app"] = iso_utc(now)
    if wants_email(user, n, now):
        label, url = email_button(n)
        if send_email(user.email, n.title, n.body, label, url):
            sent["email"] = iso_utc(now)
    n.channel_sent = sent or {"stored": iso_utc(now)}
    db.commit()
    return True


def create(db: Session, user: User, kind: str, event: Event | None, title: str, body: str, payload: dict | None = None,
           push: bool = True, bypass_quiet: bool = False, now: datetime | None = None) -> Notification | None:
    """Store a notification (deduped per user, event and type) and deliver it unless `push` is False."""
    now = now or utcnow()
    event_id = event.id if event else None
    if event_id and already_sent(db, user, event_id, kind):
        return None
    n = Notification(user_id=user.id, type=kind, event_id=event_id, title=title, body=_fit(body), payload=payload or {})
    if not push:
        n.channel_sent = {"silent": iso_utc(now)}
    db.add(n)
    db.commit()
    if push:
        deliver(db, n, user, now, bypass_quiet)
    return n


def flush_pending(db: Session, now: datetime | None = None) -> int:
    """Deliver notifications held back by quiet hours (looked at for 24 h)."""
    now = now or utcnow()
    pending = db.scalars(select(Notification).where(Notification.created_at > now - timedelta(hours=24))).all()
    count = 0
    for n in pending:
        if not n.channel_sent and not n.dismissed and n.read_at is None:
            user = db.get(User, n.user_id)
            if user and deliver(db, n, user, now):
                count += 1
    return count


# ---- suggestion triggers ----

def suggest(db: Session, event: Event, kind: str = "match", bypass_quiet: bool = False, now: datetime | None = None) -> int:
    """Tell every student this clean event fits (strict filters, match >= 75). Returns how many were notified."""
    from .feed import evaluate_one  # local: feed imports nothing from here, but keep the graph one-way

    now = now or utcnow()
    if event.status != "published" or event.verification_label == "unverified" or event.risk_score >= 30:
        return 0
    registered = set(db.scalars(select(Registration.user_id).where(Registration.event_id == event.id, Registration.status != "cancelled")))
    sent = 0
    for user in db.scalars(select(User).where(User.role == "student")).all():
        if user.id in registered or is_paused(user, now) or not any_channel(user) or already_sent(db, user, event.id, kind):
            continue
        if not user.strict_schedule:
            user = _strict(user)
        ev = evaluate_one(db, user, event)
        if not ev.result.passed or ev.dismissed or ev.scored is None or ev.scored.match < MIN_MATCH:
            continue
        if not cap_allows(db, user, kind, now):
            continue
        title, body = deadline_copy(event, now) if kind == "deadline" else match_copy(event, ev.result.distance_km)
        if create(db, db.get(User, user.id), kind, event, title, body, {"match": ev.scored.match}, bypass_quiet=bypass_quiet, now=now):
            sent += 1
    return sent


class _strict:
    """Suggestions always use strict schedule fit, whatever the user's feed setting."""

    def __init__(self, user: User):
        self._u = user

    def __getattr__(self, name):
        return True if name == "strict_schedule" else getattr(self._u, name)
