"""'Go together': friends attend together, which is the strongest nudge to actually show up.

A registered student shares an invite link. A friend who accepts is registered (or waitlisted)
and joins the inviter's group; everyone in the group sees who's coming, gets each other's name in
the leave-by reminder, and is told if someone drops out. Classmate counts are aggregate only.
"""

import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, Invite, Notification, Registration, User
from ..timeutil import utcnow
from . import notify, registration

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I lookalikes
ACTIVE = ("registered", "promoted_pending", "waitlisted", "attended")
DEPTS = {"it_dept": "IT", "cse_dept": "CSE", "ece_dept": "ECE", "mech_dept": "Mech"}


def first_name(user: User) -> str:
    return user.name.split()[0]


def names_text(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} and {len(names) - 1} others"


def companions(db: Session, reg: Registration) -> list[tuple[Registration, User]]:
    """The other people in this registration's group who are still going."""
    if not reg.group_id:
        return []
    return list(db.execute(
        select(Registration, User).join(User, User.id == Registration.user_id).where(
            Registration.group_id == reg.group_id, Registration.id != reg.id, Registration.status.in_(ACTIVE))
        .order_by(Registration.registered_at)
    ).all())


def companions_out(db: Session, reg: Registration) -> list[dict]:
    return [{"name": first_name(u), "status": r.status} for r, u in companions(db, reg)]


def invite_url(code: str) -> str:
    return f"{settings.public_url}/invite/{code}"


def create_invite(db: Session, reg: Registration) -> Invite:
    if reg.status not in ACTIVE or reg.status == "attended":
        raise HTTPException(409, "Register for the event first, then invite friends.")
    existing = db.scalar(select(Invite).where(Invite.registration_id == reg.id))
    if existing:
        return existing
    inv = Invite(code="".join(secrets.choice(CODE_CHARS) for _ in range(8)), registration_id=reg.id, event_id=reg.event_id)
    db.add(inv)
    db.commit()
    return inv


def _invite_parts(db: Session, code: str) -> tuple[Invite, Registration, User, Event]:
    inv = db.get(Invite, code.strip().upper())
    if inv is None:
        raise HTTPException(404, "That invite link doesn't work. Ask your friend to send it again.")
    reg = db.get(Registration, inv.registration_id)
    return inv, reg, db.get(User, reg.user_id), db.get(Event, inv.event_id)


def invite_info(db: Session, code: str) -> dict:
    inv, reg, inviter, event = _invite_parts(db, code)
    problem = None
    if reg.status not in ACTIVE:
        problem = f"{first_name(inviter)} isn't going anymore."
    elif event.status != "published" or event.start_at is None or event.start_at <= utcnow():
        problem = "This event has already started or isn't open."
    going = 1 + len(companions(db, reg))
    return {
        "code": inv.code,
        "inviter": first_name(inviter),
        "going": going,
        "problem": problem,
        "event": {
            "id": event.id, "title": event.title, "category": event.category, "poster_url": event.poster_url,
            "venue_name": event.venue_name, "mode": event.mode, "fee_inr": event.fee_inr,
            "start_at": event.start_at.isoformat() + "Z" if event.start_at else None,
            "end_at": event.end_at.isoformat() + "Z" if event.end_at else None,
        },
    }


def accept(db: Session, user: User, code: str) -> Registration:
    inv, inviter_reg, inviter, event = _invite_parts(db, code)
    if inviter.id == user.id:
        raise HTTPException(409, "That's your own invite. Send it to a friend.")
    if inviter_reg.status not in ACTIVE:
        raise HTTPException(409, f"{first_name(inviter)} isn't going anymore.")
    reg = registration.register(db, user, event)  # existing registration is reused
    joined_now = reg.group_id is None or reg.group_id != inviter_reg.group_id
    group = inviter_reg.group_id or str(uuid.uuid4())
    inviter_reg.group_id = reg.group_id = group
    db.commit()
    for r in [inviter_reg, reg] + [r for r, _ in companions(db, reg) if r.id != inviter_reg.id]:
        r.showup_likelihood = registration.compute_likelihood(db, db.get(User, r.user_id), event, r).p
    db.commit()
    if joined_now:
        for other, person in companions(db, reg):
            _send(db, person, "buddy_joined", event, f"{first_name(user)} is going with you",
                  f"{notify._short(event.title)}. You'll see each other's plans on your pass.", {"registration_id": other.id})
    return reg


def notify_cancel(db: Session, reg: Registration) -> None:
    """Tell the rest of the group someone dropped out (before the seat goes to the waitlist)."""
    person = db.get(User, reg.user_id)
    event = db.get(Event, reg.event_id)
    for other, friend in companions(db, reg):
        _send(db, friend, "buddy_cancelled", event, f"{first_name(person)} can't make it",
              f"{notify._short(event.title)}. You're still going.", {"registration_id": other.id})


def _send(db: Session, user: User, kind: str, event: Event, title: str, body: str, payload: dict) -> None:
    # Not deduped like suggestions: each friend joining or leaving is news.
    n = Notification(user_id=user.id, type=kind, event_id=event.id, title=title, body=notify._fit(body), payload=payload)
    db.add(n)
    db.commit()
    notify.deliver(db, n, user)


def classmates_going(db: Session, user: User, event_ids: list[str]) -> dict[str, dict]:
    """'3 from IT, year 3 are going': a count of people sharing the user's department and year. Never names."""
    tags = set(user.eligibility_tags or [])
    dept = next((t for t in tags if t in DEPTS), None)
    year = next((t for t in tags if t.startswith("year_")), None)
    if not dept or not year or not event_ids:
        return {}
    rows = db.execute(
        select(Registration.event_id, User.eligibility_tags).join(User, User.id == Registration.user_id).where(
            Registration.event_id.in_(event_ids), Registration.user_id != user.id,
            Registration.status.in_(("registered", "promoted_pending", "attended")))
    ).all()
    counts: dict[str, int] = {}
    for event_id, their in rows:
        if dept in (their or []) and year in (their or []):
            counts[event_id] = counts.get(event_id, 0) + 1
    label = f"{DEPTS[dept]}, year {year.removeprefix('year_')}"
    return {eid: {"count": n, "label": label} for eid, n in counts.items()}
