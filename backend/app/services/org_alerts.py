"""Alerts for organizers (settings group 3): new registrations, cancellations, waitlist changes,
admin review results and event reminders. Each type can be switched off. With the daily digest on,
registration, cancellation and waitlist alerts are collected and sent as one summary per day instead
of one alert each (busy events would otherwise be spam). Channels, quiet hours and pause are the
organizer's own user settings, same as for students.
"""

from collections import Counter
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, Notification, Organizer, User
from ..timeutil import iso_utc, ist_to_utc, to_ist, utcnow

# preference key -> notification type
PREFS = {
    "new_registration": "org_registration",
    "cancellation": "org_cancellation",
    "waitlist_change": "org_waitlist",
    "new_message": "new_message",
    "review_result": "org_review",
    "event_reminders": "org_reminder",
}
DEFAULT_PREFS = {k: True for k in PREFS}
DIGESTIBLE = {"org_registration", "org_cancellation", "org_waitlist"}
DIGEST_HOUR_IST = 19  # one summary at 7 PM


def prefs_of(org: Organizer) -> dict:
    return {**DEFAULT_PREFS, **(org.notif_prefs or {})}


def wants(org: Organizer, kind: str) -> bool:
    key = next((k for k, v in PREFS.items() if v == kind), None)
    return key is None or bool(prefs_of(org).get(key, True))


def alert(db: Session, event: Event, kind: str, title: str, body: str, now: datetime | None = None) -> Notification | None:
    """Tell the event's organizer. Not deduplicated: every registration is its own alert (or digest line)."""
    from . import notify

    now = now or utcnow()
    org = event.organizer
    if org is None or not wants(org, kind):
        return None
    user = db.get(User, org.user_id)
    if user is None:
        return None
    n = Notification(user_id=user.id, type=kind, event_id=event.id, title=title, body=notify._fit(body), payload={})
    if org.daily_digest and kind in DIGESTIBLE:
        n.channel_sent = {"digest": "pending"}  # held for the daily summary
        db.add(n)
        db.commit()
        return n
    db.add(n)
    db.commit()
    notify.deliver(db, n, user, now)
    return n


def _short(title: str) -> str:
    return title if len(title) <= 34 else title[:33].rstrip() + "…"


def registered(db: Session, event: Event, waitlisted: bool, name: str) -> None:
    if waitlisted:
        alert(db, event, "org_waitlist", "Someone joined the waitlist", f"{name} is on the waitlist for {_short(event.title)}.")
    else:
        alert(db, event, "org_registration", "New registration", f"{name} registered for {_short(event.title)}.")


def cancelled(db: Session, event: Event, name: str, promoted: int) -> None:
    extra = " A seat was offered to the waitlist." if promoted else ""
    alert(db, event, "org_cancellation", "A registration was cancelled", f"{name} can't make it to {_short(event.title)}.{extra}")


def seat_confirmed(db: Session, event: Event, name: str) -> None:
    alert(db, event, "org_waitlist", "Waitlist seat confirmed", f"{name} took the open seat at {_short(event.title)}.")


def review_result(db: Session, event: Event, approved: bool) -> None:
    if approved:
        alert(db, event, "org_review", "Your event is live", f"{_short(event.title)} was approved and is now published.")
    else:
        alert(db, event, "org_review", "Your event wasn't approved", f"{_short(event.title)} was not approved. Open it to see why.")


def verification_result(db: Session, org: Organizer, approved: bool) -> None:
    from . import notify

    if not wants(org, "org_review"):
        return
    user = db.get(User, org.user_id)
    title = "Your organization is verified" if approved else "Verification wasn't approved"
    body = ("Your events now show a Verified organizer label." if approved
            else "We couldn't verify your organization from that document. You can send another.")
    n = Notification(user_id=user.id, type="org_review", title=title, body=body, payload={})
    db.add(n)
    db.commit()
    notify.deliver(db, n, user)


def send_event_reminders(db: Session, now: datetime) -> int:
    """24 hours before each of an organizer's events: one reminder with the current registration count."""
    from . import notify
    from .feed import registered_counts

    events = db.scalars(select(Event).where(
        Event.status == "published", Event.event_type != "internship",
        Event.start_at > now, Event.start_at <= now + timedelta(hours=24),
    )).unique().all()
    counts = registered_counts(db, [e.id for e in events]) if events else {}
    sent = 0
    for e in events:
        org = e.organizer
        if org is None or not wants(org, "org_reminder"):
            continue
        user = db.get(User, org.user_id)
        if notify.already_sent(db, user, e.id, "org_reminder"):
            continue
        n = counts.get(e.id, 0)
        start = to_ist(e.start_at)
        if alert(db, e, "org_reminder", f"Tomorrow: {_short(e.title)}" if (start.date() - to_ist(now).date()).days == 1 else f"Coming up: {_short(e.title)}",
                 f"{n} registered. Open check-in when doors open."):
            sent += 1
    return sent


def send_digests(db: Session, now: datetime) -> int:
    """Once a day after 7 PM IST: one summary per organizer of the alerts held for the digest."""
    from . import notify

    local = to_ist(now)
    if local.time() < time(DIGEST_HOUR_IST, 0):
        return 0
    day_start = ist_to_utc(local.date(), 0)
    pending = db.scalars(select(Notification).where(Notification.type.in_(DIGESTIBLE), Notification.created_at > now - timedelta(days=2))).all()
    by_user: dict[str, list[Notification]] = {}
    for n in pending:
        if (n.channel_sent or {}).get("digest") == "pending":
            by_user.setdefault(n.user_id, []).append(n)
    sent = 0
    for user_id, items in by_user.items():
        user = db.get(User, user_id)
        if user is None:
            continue
        already = db.scalar(select(Notification.id).where(Notification.user_id == user_id, Notification.type == "org_digest",
                                                          Notification.created_at >= day_start).limit(1))
        if already:
            continue
        c = Counter(n.type for n in items)
        parts = []
        if c["org_registration"]:
            parts.append(f"{c['org_registration']} new registration{'s' if c['org_registration'] != 1 else ''}")
        if c["org_cancellation"]:
            parts.append(f"{c['org_cancellation']} cancellation{'s' if c['org_cancellation'] != 1 else ''}")
        if c["org_waitlist"]:
            parts.append(f"{c['org_waitlist']} waitlist change{'s' if c['org_waitlist'] != 1 else ''}")
        events = len({n.event_id for n in items})
        digest = Notification(user_id=user_id, type="org_digest", title="Today on ShowUp",
                              body=notify._fit(f"{', '.join(parts)} across {events} event{'s' if events != 1 else ''}."), payload={})
        db.add(digest)
        for n in items:
            n.channel_sent = {"digest": iso_utc(now)}
        db.commit()
        notify.deliver(db, digest, user, now)
        sent += 1
    return sent
