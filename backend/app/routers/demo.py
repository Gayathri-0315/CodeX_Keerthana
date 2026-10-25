"""Demo panel actions (SPEC 12). Only in DEMO_MODE; they act on the seeded demo accounts."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import Event, Notification, Registration, User
from ..services import feedcache, jobs, listing, notify, registration, together
from ..services.extraction import SEED_DIR, resolve_mock_poster
from ..timeutil import ist_today, utcnow

router = APIRouter(prefix="/demo", tags=["demo"])
SAMPLE = "ai_workshop"
FULL_EVENT = "Startup Pitch Night"


def demo_only(user: User = Depends(current_user)) -> User:
    if not settings.demo_mode:
        raise HTTPException(404, "Not found.")
    return user


def _user(db: Session, email: str) -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u is None:
        raise HTTPException(503, "Demo data is missing. Reset the demo and try again.")
    return u


@router.post("/publish-ai-workshop")
def publish_ai_workshop(_: User = Depends(demo_only), db: Session = Depends(get_db)):
    """Publishes the sample AI Workshop as the demo club and sends match alerts right away."""
    org = _user(db, "organizer@demo.app").organizer
    spec = resolve_mock_poster(json.loads((SEED_DIR / "posters" / f"{SAMPLE}.json").read_text(encoding="utf-8")), ist_today())
    event = db.scalar(select(Event).where(Event.organizer_id == org.id, Event.title == spec["title"], Event.status != "cancelled"))
    if event is None:
        event = Event(organizer_id=org.id, status="draft")
        listing.apply_form(db, event, listing.form_from_extraction(spec, None, "web_upload"))
        db.add(event)
        db.flush()
    if event.status != "published":
        a = listing.run_gate(db, org, event, event.id)
        event.risk_score, event.risk_reasons = a.score, a.reasons
        event.status, event.verification_label = listing.predicted_outcome(db, org, a, event.id)
        event.published_at = utcnow()
    # Re-running the demo should alert again, so forget earlier alerts for this event.
    db.execute(delete(Notification).where(Notification.event_id == event.id, Notification.type == "match"))
    db.commit()
    feedcache.invalidate_all()
    sent = notify.suggest(db, event, bypass_quiet=True)
    return {"event_id": event.id, "status": event.status, "notified": sent}


@router.post("/release-seat")
def release_seat(_: User = Depends(demo_only), db: Session = Depends(get_db)):
    """Puts the demo student first on the full event's waitlist, then someone else cancels."""
    student = _user(db, "student@demo.app")
    event = db.scalar(select(Event).where(Event.title == FULL_EVENT, Event.status == "published"))
    if event is None:
        raise HTTPException(409, "The full demo event isn't available. Reset the demo.")
    mine = registration.active_registration(db, student.id, event.id)
    if mine and mine.status != "waitlisted":
        raise HTTPException(409, "The demo student already has a seat. Cancel it or reset the demo first.")
    if mine is None:
        mine = Registration(user_id=student.id, event_id=event.id, status="waitlisted", waitlist_position=0, registered_at=utcnow())
        db.add(mine)
    else:
        mine.waitlist_position = 0
    db.commit()
    seat = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.status == "registered",
                                                Registration.user_id != student.id).limit(1))
    if seat is None:
        raise HTTPException(409, "Nobody holds a seat to release.")
    promoted = registration.cancel(db, seat)
    jobs.offer_seats(db, promoted)
    return {"event_id": event.id, "promoted": [r.user_id == student.id for r in promoted]}


@router.post("/leave-by")
def fast_forward_leave_by(_: User = Depends(demo_only), db: Session = Depends(get_db)):
    """Sends the demo student's next leave-by reminder now."""
    student = _user(db, "student@demo.app")
    row = db.execute(
        select(Registration, Event).join(Event, Event.id == Registration.event_id)
        .where(Registration.user_id == student.id, Registration.status == "registered", Event.start_at > utcnow(), Event.mode == "in_person")
        .order_by(Event.start_at).limit(1)
    ).first()
    if row is None:
        raise HTTPException(409, "Register the demo student for an in-person event first.")
    reg, event = row
    db.execute(delete(Notification).where(Notification.event_id == event.id, Notification.user_id == student.id, Notification.type == "reminder_leave_by"))
    db.commit()
    friends = [together.first_name(u) for _, u in together.companions(db, reg)]
    title, body = notify.reminder_copy("reminder_leave_by", event, registration.leave_by_for(student, event), friends)
    maps = f"https://www.google.com/maps/dir/?api=1&destination={event.lat},{event.lng}"
    notify.create(db, student, "reminder_leave_by", event, title, body, {"registration_id": reg.id, "maps_url": maps}, bypass_quiet=True)
    return {"event_id": event.id}


@router.post("/friend-joins")
def friend_joins(_: User = Depends(demo_only), db: Session = Depends(get_db)):
    """A classmate accepts the demo student's 'Go together' invite for their next event."""
    student = _user(db, "student@demo.app")
    reg = db.scalar(
        select(Registration).join(Event, Event.id == Registration.event_id)
        .where(Registration.user_id == student.id, Registration.status == "registered", Event.start_at > utcnow())
        .order_by(Event.start_at).limit(1)
    )
    if reg is None:
        raise HTTPException(409, "Register the demo student for an event first.")
    taken = set(db.scalars(select(Registration.user_id).where(Registration.event_id == reg.event_id, Registration.status != "cancelled")))
    candidates = [u for u in db.scalars(select(User).where(User.role == "student", User.email != student.email)) if u.id not in taken]
    if not candidates:
        raise HTTPException(409, "Every demo student is already going to that event.")
    # Prefer a classmate (same department and year) so the card's "from IT, year 3" count moves too.
    mine = set(student.eligibility_tags or [])
    friend = max(candidates, key=lambda u: len(mine & set(u.eligibility_tags or [])))
    invite = together.create_invite(db, reg)
    together.accept(db, friend, invite.code)
    return {"event_id": reg.event_id, "friend": together.first_name(friend)}


@router.post("/reset")
def reset(_: User = Depends(demo_only)):
    from ..seed.seed import reset_and_seed

    return reset_and_seed()
