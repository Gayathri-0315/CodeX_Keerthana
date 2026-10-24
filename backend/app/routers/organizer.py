from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role, upload_limit
from ..models import Event, Organizer, Registration, User
from ..schemas import AppealIn, EventIn
from ..services import feedcache, listing
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
    org = my_org(user)
    event = my_event(db, user, event_id)
    if event.status in ("published", "cancelled"):
        raise HTTPException(409, "This event is already " + ("live." if event.status == "published" else "cancelled."))
    missing = [name for name, ok in (("a title", event.title), ("a date and start time", event.start_at)) if not ok]
    if event.mode == "in_person" and not event.venue_name:
        missing.append("a venue")
    if missing:
        raise HTTPException(422, f"Add {' and '.join(missing)} before publishing.")

    assessment = listing.run_gate(db, org, event, event.id)
    event.risk_score, event.risk_reasons, event.duplicate_of = assessment.score, assessment.reasons, assessment.duplicate_of
    status, label = listing.predicted_outcome(db, org, assessment, event.id)
    event.status, event.verification_label = status, label
    if status == "published":
        event.published_at = utcnow()
    db.commit()
    feedcache.invalidate_all()
    return {**event_out(db, event), "message": STATUS_MESSAGES[status]}


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
