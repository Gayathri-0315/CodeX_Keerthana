"""After-event follow-up (feature 2): the morning after an event, ONE "How was it?" alert to each student an
organizer checked in, with a one-tap thumbs up or down and one suggested next event. No-shows get nothing.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Event, Feedback, Organizer, Registration, User
from ..timeutil import ist_to_utc, to_ist

SEND_FROM, SEND_UNTIL = time(10, 0), time(21, 0)  # local time; the scheduler sends once inside this window
SKILL_UP = {"beginner": "intermediate", "intermediate": "advanced"}
MIN_ANSWERS = 3  # aggregate shown to organizers only from this many answers, so nobody can be singled out


def suggest_next(db: Session, user: User, attended: Event) -> Event | None:
    """Best match from For you: same category or same club first, then one skill level up, then match score."""
    from .feed import evaluate

    up = SKILL_UP.get(attended.skill_level or "")
    best, best_key = None, None
    for i in evaluate(db, user).for_you():
        e = i.event
        if e.id == attended.id:
            continue
        related = (attended.category_slug and e.category_slug == attended.category_slug) or (e.organizer_id == attended.organizer_id)
        key = (bool(related), bool(up and e.skill_level == up), i.scored.match if i.scored else 0)
        if best_key is None or key > best_key:
            best, best_key = e, key
    return best


def how_was_copy(event: Event) -> tuple[str, str]:
    from .notify import _fit, _short

    return _fit(f"How was {_short(event.title, 36)}?"), "Tap a thumb. It helps the next students choose."


def send_how_was(db: Session, now: datetime) -> int:
    """Once, the day after the event, between 10 AM and 9 PM local time."""
    from . import notify

    local = to_ist(now)
    if not (SEND_FROM <= local.time() < SEND_UNTIL):
        return 0
    yesterday = local.date() - timedelta(days=1)
    rows = db.execute(
        select(Registration, Event).join(Event, Event.id == Registration.event_id).where(
            Registration.status == "attended",
            Event.end_at >= ist_to_utc(yesterday, 0), Event.end_at < ist_to_utc(local.date(), 0),
        )
    ).unique().all()
    sent = 0
    for reg, event in rows:
        user = db.get(User, reg.user_id)
        if user is None or notify.is_paused(user, now) or not notify.any_channel(user):
            continue
        if notify.already_sent(db, user, event.id, "how_was"):
            continue
        nxt = suggest_next(db, user, event)
        payload = {"registration_id": reg.id}
        if nxt:
            payload["suggested"] = {"event_id": nxt.id, "title": nxt.title}
        title, body = how_was_copy(event)
        if nxt:
            body = notify._fit(f"Tap a thumb. Next up for you: {notify._short(nxt.title, 40)}.")
        if notify.create(db, user, "how_was", event, title, body, payload, now=now):
            sent += 1
    return sent


def described_stats(db: Session, event_ids: list[str]) -> tuple[int, int]:
    """(matched the description, answers) across these events; only from attended students."""
    if not event_ids:
        return 0, 0
    rows = dict(db.execute(
        select(Feedback.kind, func.count()).where(Feedback.event_id.in_(event_ids), Feedback.kind.in_(("as_described", "not_as_described")))
        .group_by(Feedback.kind)
    ).all())
    yes = rows.get("as_described", 0)
    return yes, yes + rows.get("not_as_described", 0)


def organizer_described_ok(db: Session, org: Organizer) -> bool:
    """Trust: an organizer whose events mostly didn't match their description isn't promoted."""
    ids = list(db.scalars(select(Event.id).where(Event.organizer_id == org.id)))
    yes, total = described_stats(db, ids)
    return total < MIN_ANSWERS or yes / total >= 0.5
