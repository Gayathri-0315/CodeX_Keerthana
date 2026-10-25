from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..models import Event, Organizer, Report, User
from ..services import feedcache, jobs
from ..timeutil import iso_utc, utcnow

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_role("admin")


def open_reports(db: Session, e: Event) -> list[Report]:
    q = select(Report).where(Report.event_id == e.id)
    if e.reviewed_at:
        q = q.where(Report.created_at > e.reviewed_at)
    return list(db.scalars(q.order_by(Report.created_at)))


@router.get("/review-queue")
def review_queue(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    reported_ids = select(Report.event_id).distinct()
    events = db.scalars(
        select(Event)
        .where(or_(Event.status == "pending_review", Event.id.in_(reported_ids), Event.appeal_note.is_not(None) & (Event.status == "blocked")))
        .order_by(Event.created_at.desc())
    ).unique().all()
    items = []
    for e in events:
        reports = open_reports(db, e)
        if e.status != "pending_review" and not reports:
            continue  # reports already settled by an earlier decision
        org = e.organizer
        items.append({
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "status": e.status,
            "start_at": iso_utc(e.start_at),
            "fee_inr": e.fee_inr,
            "registration_url": e.registration_url,
            "poster_url": e.poster_url,
            "risk_score": e.risk_score,
            "risk_reasons": e.risk_reasons or [],
            "appeal_note": e.appeal_note,
            "reports": [{"reason": r.reason, "at": iso_utc(r.created_at)} for r in reports],
            "organizer": {"id": org.id, "name": org.org_name, "trust_level": org.trust_level, "email_domain": org.org_email_domain} if org else None,
        })
    return {"items": items}


def _decide(db: Session, event_id: str, approve: bool) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "That event doesn't exist.")
    if approve:
        org = event.organizer
        event.status = "published"
        # An admin checked the details; only the organizer's own verification earns the stronger label.
        event.verification_label = "organizer_verified" if org and org.trust_level in ("verified", "trusted") else "details_reviewed"
        event.published_at = event.published_at or utcnow()
    else:
        event.status = "blocked"
        event.verification_label = "unverified"
    event.appeal_note = None
    event.reviewed_at = utcnow()
    db.commit()
    feedcache.invalidate_all()
    return event


@router.post("/events/{event_id}/approve")
def approve(event_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    from .organizer import suggest_in_background

    event = _decide(db, event_id, True)
    jobs.in_background(suggest_in_background, event.id)
    return {"id": event.id, "status": "published"}


@router.post("/events/{event_id}/reject")
def reject(event_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return {"id": _decide(db, event_id, False).id, "status": "blocked"}


@router.post("/organizers/{organizer_id}/verify")
def verify_organizer(organizer_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    org = db.get(Organizer, organizer_id)
    if org is None:
        raise HTTPException(404, "That organizer doesn't exist.")
    if org.trust_level == "new":
        org.trust_level = "verified"
    org.verified_by = user.id
    db.commit()
    feedcache.invalidate_all()
    return {"id": org.id, "trust_level": org.trust_level}
