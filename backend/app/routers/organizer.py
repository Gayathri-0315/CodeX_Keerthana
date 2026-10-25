from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role, upload_limit
from ..models import Event, Notification, Organizer, Registration, User
from ..schemas import AppealIn, EventIn
from ..services import feedcache, listing, notify, registration, showup_score
from ..services.extraction import extract_poster
from ..services.feed import SEAT_STATUSES
from ..services.uploads import public_url, read_upload
from ..timeutil import iso_utc, utcnow

router = APIRouter(prefix="/organizer", tags=["organizer"])
organizer_only = require_role("organizer")

STATUS_MESSAGES = {
    "published": "Your event is live.",
    "pending_review": "Submitted for review. We'll publish it once an admin checks it.",
    "blocked": "We couldn't publish this event. Fix the issues below and try again, or appeal.",
}


def my_org(user: User) -> Organizer:
    if user.organizer is None:
        raise HTTPException(403, "Set up your organizer profile first.")
    return user.organizer


def my_event(db: Session, user: User, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.organizer_id != my_org(user).id:
        raise HTTPException(404, "That event doesn't exist or isn't yours.")
    return event


def risk_out(a) -> dict:
    return {"score": a.score, "level": a.level, "reasons": a.reasons, "duplicate_of": a.duplicate_of}


def event_out(db: Session, e: Event) -> dict:
    seats = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id, Registration.status.in_(SEAT_STATUSES)))
    return {
        "id": e.id,
        "status": e.status,
        "verification_label": e.verification_label,
        "risk": {"score": e.risk_score, "level": "low" if e.risk_score < 30 else "medium" if e.risk_score < 60 else "high",
                 "reasons": e.risk_reasons or [], "duplicate_of": e.duplicate_of},
        "start_at": iso_utc(e.start_at),
        "end_at": iso_utc(e.end_at),
        "seats_taken": seats or 0,
        "appeal_note": e.appeal_note,
        "published_at": iso_utc(e.published_at),
        "form": listing.event_form(e),
    }


@router.get("/summary")
def summary(user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    org = my_org(user)
    now = utcnow()
    events = db.scalars(select(Event).where(Event.organizer_id == org.id)).unique().all()
    ids = [e.id for e in events]
    regs = db.execute(
        select(Registration.status, func.count()).where(Registration.event_id.in_(ids)).group_by(Registration.status)
    ).all() if ids else []
    by_status = dict(regs)
    return {
        "org_name": org.org_name,
        "trust_level": org.trust_level,
        "upcoming": sum(1 for e in events if e.status == "published" and e.start_at and e.start_at > now),
        "registrations": sum(by_status.get(s, 0) for s in SEAT_STATUSES),
        "attendance_rate": org.avg_attendance_rate,
    }


@router.get("/events")
def list_events(user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    org = my_org(user)
    events = db.scalars(select(Event).where(Event.organizer_id == org.id).order_by(Event.start_at.desc().nulls_last())).unique().all()
    return {"events": [event_out(db, e) for e in events]}


@router.get("/events/{event_id}")
def get_event(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    return event_out(db, my_event(db, user, event_id))


@router.get("/samples")
def samples(user: User = Depends(organizer_only)):
    from ..seed.make_samples import sample_posters

    return {"posters": [{**s, "url": f"/api/samples/posters/{s['name']}.png"} for s in sample_posters()]}


@router.post("/events/extract", dependencies=[Depends(upload_limit)])
def extract(file: UploadFile = File(...), user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Poster upload -> draft fields. Never fails hard: on trouble it returns empty fields and a message."""
    my_org(user)
    upload = read_upload(file.file.read(), file.filename or "poster")
    return {**extract_poster(db, upload), "poster_url": public_url(upload.stored_name)}


@router.post("/events/preview")
def preview(body: EventIn, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Live trust check and reach for an unsaved form."""
    org = my_org(user)
    draft = listing.draft_from_form(db, body, org)
    assessment = listing.run_gate(db, org, draft, None)
    status, label = listing.predicted_outcome(db, org, assessment, None)
    return {"risk": risk_out(assessment), "outcome": {"status": status, "label": label}, "reach": listing.reach(db, draft)}


@router.post("/events")
def save_event(body: EventIn, event_id: str | None = None, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Create (no id) or update a draft. Runs the trust gate; a live event that turns high risk is pulled."""
    org = my_org(user)
    if not body.title.strip():
        raise HTTPException(422, "Add a title before saving.")
    event = my_event(db, user, event_id) if event_id else Event(organizer_id=org.id, status="draft")
    if event.status == "cancelled":
        raise HTTPException(409, "This event was cancelled and can't be edited.")
    listing.apply_form(db, event, body)
    if event_id is None:
        db.add(event)
        db.flush()
    assessment = listing.run_gate(db, org, event, event.id)
    event.risk_score, event.risk_reasons, event.duplicate_of = assessment.score, assessment.reasons, assessment.duplicate_of
    if event.status == "published":
        status, label = listing.predicted_outcome(db, org, assessment, event.id)
        event.status, event.verification_label = ("blocked", "unverified") if status == "blocked" else ("published", label)
    db.commit()
    feedcache.invalidate_all()
    return event_out(db, event)


@router.post("/events/{event_id}/publish")
def publish(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    status = listing.publish(db, my_org(user), my_event(db, user, event_id))
    return {**event_out(db, db.get(Event, event_id)), "message": STATUS_MESSAGES[status]}


class MessageIn(BaseModel):
    text: str = Field(min_length=3, max_length=200)


class CheckinIn(BaseModel):
    token: str = Field(min_length=4, max_length=64)  # the QR's token, or the 6-character code


@router.get("/events/{event_id}/registrations")
def event_registrations(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Registrants for this organizer only. Never public.

    Deliberately no per-person show-up score: rating individual students on reliability invites
    unfair treatment and is mostly noise at pilot scale. The aggregate estimate is in /analytics.
    """
    event = my_event(db, user, event_id)
    rows = db.execute(
        select(Registration, User).join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event.id, Registration.status != "cancelled")
        .order_by(Registration.waitlist_position.nulls_first(), Registration.registered_at)
    ).all()
    return {"registrations": [{
        "id": reg.id, "name": person.name, "status": reg.status, "waitlist_position": reg.waitlist_position,
        "registered_at": iso_utc(reg.registered_at), "checked_in_at": iso_utc(reg.checked_in_at),
        "external": reg.external, "with_friends": reg.group_id is not None,
    } for reg, person in rows]}


@router.get("/events/{event_id}/analytics")
def analytics(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Predicted (sum of likelihoods, with a rough range) vs actual check-ins."""
    event = my_event(db, user, event_id)
    rows = db.execute(
        select(Registration, User).join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event.id, Registration.status.in_(("registered", "promoted_pending", "attended", "no_show")))
    ).all()
    ps = [registration.compute_likelihood(db, person, event, reg).p for reg, person in rows]
    expected, low, high = showup_score.expected_turnout(ps)
    waitlisted = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event.id, Registration.status == "waitlisted"))
    return {
        "registered": len(ps),
        "capacity": event.capacity,
        "waitlisted": waitlisted or 0,
        "expected": expected,
        "expected_low": low,
        "expected_high": high,
        "actual": sum(1 for reg, _ in rows if reg.status == "attended"),
        "ended": bool(event.end_at and event.end_at < utcnow()),
    }


@router.post("/events/{event_id}/message")
def message(event_id: str, body: MessageIn, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    event = my_event(db, user, event_id)
    people = db.scalars(select(User).join(Registration, Registration.user_id == User.id).where(
        Registration.event_id == event.id, Registration.status.in_(("registered", "promoted_pending", "waitlisted")))).all()
    for person in people:
        n = Notification(user_id=person.id, type="message", event_id=event.id, title=f"From {my_org(user).org_name}", body=body.text.strip())
        db.add(n)
        db.commit()
        notify.deliver(db, n, person)
    return {"sent": len(people)}


@router.post("/events/{event_id}/cancel")
def cancel_event(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    event = my_event(db, user, event_id)
    if event.status == "cancelled":
        return event_out(db, event)
    regs = db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.status.in_(registration.ACTIVE))).all()
    now = utcnow()
    event.status = "cancelled"
    for r in regs:
        r.status, r.cancelled_at, r.waitlist_position, r.promotion_expires_at = "cancelled", now, None, None
    db.commit()
    feedcache.invalidate_all()
    for r in regs:
        person = db.get(User, r.user_id)
        notify.create(db, person, "cancelled_event", event, "Event cancelled", f"{event.title} was cancelled by the organizer.", bypass_quiet=True)
    return {**event_out(db, event), "notified": len(regs)}


@router.post("/events/{event_id}/checkin")
def checkin(event_id: str, body: CheckinIn, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """Accepts the QR token or the short manual code. Checking someone in twice is harmless."""
    event = my_event(db, user, event_id)
    raw = body.token.strip()
    reg = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.checkin_token == raw))
    if reg is None and len(raw) == 6:
        code = raw.upper()
        reg = next((r for r in db.scalars(select(Registration).where(Registration.event_id == event.id)) if r.checkin_code == code), None)
    if reg is None:
        raise HTTPException(404, "That pass isn't for this event.")
    person = db.get(User, reg.user_id)
    if reg.status == "attended":
        return {"name": person.name, "status": "already", "checked_in_at": iso_utc(reg.checked_in_at), "count": _attended(db, event.id)}
    if reg.status not in ("registered", "promoted_pending", "no_show"):
        raise HTTPException(409, f"{person.name} isn't registered ({reg.status.replace('_', ' ')}).")
    reg.status, reg.checked_in_at = "attended", utcnow()
    db.commit()
    return {"name": person.name, "status": "checked_in", "checked_in_at": iso_utc(reg.checked_in_at), "count": _attended(db, event.id)}


def _attended(db: Session, event_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event_id, Registration.status == "attended")) or 0


@router.get("/events/{event_id}/reach-preview")
def reach_preview(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    return listing.reach(db, my_event(db, user, event_id))


@router.post("/events/{event_id}/appeal")
def appeal(event_id: str, body: AppealIn, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    event = my_event(db, user, event_id)
    if event.status != "blocked":
        raise HTTPException(409, "Only blocked events can be appealed.")
    event.appeal_note = body.note.strip()
    event.status = "pending_review"
    db.commit()
    return {**event_out(db, event), "message": "Appeal sent. An admin will review it."}
