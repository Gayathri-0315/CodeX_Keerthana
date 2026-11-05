from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..errors import fail
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
    event = _decide(db, event_id, True)
    from ..services import org_alerts

    org_alerts.review_result(db, event, True)
    jobs.in_background(jobs.suggest_for_event, event.id)
    return {"id": event.id, "status": "published"}


@router.post("/events/{event_id}/reject")
def reject(event_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    event = _decide(db, event_id, False)
    from ..services import org_alerts

    org_alerts.review_result(db, event, False)
    return {"id": event.id, "status": "blocked"}


@router.post("/test-email")
def test_email(user: User = Depends(admin_only)):
    """Send a test email to the signed-in admin, to check EMAIL_PROVIDER / EMAIL_API_KEY / EMAIL_FROM."""
    from ..config import settings
    from ..services.email import email_configured, send_email

    if not email_configured():
        send_email(user.email, "ShowUp test email", "If you can read this, email works.", "Open ShowUp", settings.public_url,
                   transactional=True)
        return {"status": "skipped", "to": user.email,
                "message": "No email provider is set, so it went to the server log (look for 'email skipped')."}
    ok = send_email(user.email, "ShowUp test email", "If you can read this, email works.", "Open ShowUp", settings.public_url,
                    transactional=True)
    if not ok:
        fail(400, "email_failed", f"The {settings.email_provider} API refused the email. Check the key and that EMAIL_FROM is a verified sender; the server log has the details.")
    return {"status": "sent", "to": user.email, "message": f"Sent to {user.email} through {settings.email_provider}."}


@router.post("/organizers/{organizer_id}/verify")
def verify_organizer(organizer_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    org = db.get(Organizer, organizer_id)
    if org is None:
        raise HTTPException(404, "That organizer doesn't exist.")
    set_trust(db, org, "verified" if org.trust_level == "new" else org.trust_level, user)
    return {"id": org.id, "trust_level": org.trust_level}


# ---- organizer verification requests (organizer settings: "Verify organization") ----

@router.get("/verification-requests")
def verification_requests(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    from ..models import OrgVerificationRequest

    rows = db.scalars(select(OrgVerificationRequest).where(OrgVerificationRequest.status == "pending")
                      .order_by(OrgVerificationRequest.created_at)).all()
    out = []
    for r in rows:
        org = db.get(Organizer, r.organizer_id)
        owner = db.get(User, org.user_id) if org else None
        out.append({
            "id": r.id, "document_type": r.document_type, "note": r.note, "submitted_at": iso_utc(r.created_at),
            "organizer": {"id": org.id, "name": org.org_name, "email": owner.email if owner else None,
                          "college_or_company": org.college_or_company, "faculty_name": org.faculty_name,
                          "faculty_email": org.faculty_email, "trust_level": org.trust_level} if org else None,
        })
    return {"items": out}


@router.get("/verification-requests/{request_id}/document")
def verification_document(request_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """The uploaded proof. Admins only; never served on a public URL."""
    from fastapi.responses import Response

    from ..models import OrgVerificationRequest, StoredFile

    r = db.get(OrgVerificationRequest, request_id)
    f = db.get(StoredFile, r.document_name) if r else None
    if f is None:
        raise HTTPException(404, "That document doesn't exist.")
    return Response(f.data, media_type=f.content_type, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


def _decide_verification(db: Session, request_id: str, admin: User, approve: bool) -> dict:
    from ..models import OrgVerificationRequest
    from ..services import org_alerts

    r = db.get(OrgVerificationRequest, request_id)
    if r is None or r.status != "pending":
        raise HTTPException(404, "That request isn't waiting for review.")
    org = db.get(Organizer, r.organizer_id)
    r.status, r.decided_by, r.decided_at = ("approved" if approve else "rejected"), admin.id, utcnow()
    if approve and org.trust_level == "new":
        org.trust_level, org.verified_by = "verified", admin.id
    db.commit()
    feedcache.invalidate_all()
    org_alerts.verification_result(db, org, approve)
    return {"id": r.id, "status": r.status, "trust_level": org.trust_level}


@router.post("/verification-requests/{request_id}/approve")
def approve_verification(request_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _decide_verification(db, request_id, user, True)


@router.post("/verification-requests/{request_id}/reject")
def reject_verification(request_id: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return _decide_verification(db, request_id, user, False)


# ---- reported group chat messages ----

@router.get("/chat-reports")
def chat_reports(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    from ..models import ChatMessage, ChatReport

    rows = db.execute(select(ChatReport, ChatMessage, Event).join(ChatMessage, ChatMessage.id == ChatReport.message_id)
                      .join(Event, Event.id == ChatMessage.event_id).where(ChatReport.status == "open")
                      .order_by(ChatReport.created_at)).all()
    return {"items": [{"id": r.id, "reason": r.reason, "message": m.body, "message_id": m.id, "event_title": e.title,
                       "at": iso_utc(r.created_at)} for r, m, e in rows]}


@router.post("/chat-reports/{report_id}/{action}")
def decide_chat_report(report_id: str, action: str, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    from ..models import ChatMessage, ChatReport

    if action not in ("hide", "dismiss"):
        raise HTTPException(404, "Unknown action.")
    r = db.get(ChatReport, report_id)
    if r is None:
        raise HTTPException(404, "That report doesn't exist.")
    m = db.get(ChatMessage, r.message_id)
    if action == "hide" and m:
        m.hidden_reason, m.pinned = "Removed by ShowUp", False
    for other in db.scalars(select(ChatReport).where(ChatReport.message_id == r.message_id, ChatReport.status == "open")):
        other.status = "hidden" if action == "hide" else "dismissed"
    db.commit()
    return {"status": r.status}


# ---- every organizer, so an admin can verify (or un-verify) anyone ----

class TrustIn(BaseModel):
    level: Literal["new", "verified", "trusted"]


def set_trust(db: Session, org: Organizer, level: str, admin: User) -> None:
    """Change an organizer's trust level and bring their events' badge in line with it."""
    from ..services import org_alerts

    was_verified = org.trust_level in ("verified", "trusted")
    org.trust_level = level
    org.verified_by = admin.id if level != "new" else None
    verified = level in ("verified", "trusted")
    for e in db.scalars(select(Event).where(Event.organizer_id == org.id)):
        if verified and e.verification_label == "details_reviewed":
            e.verification_label = "organizer_verified"
        elif not verified and e.verification_label == "organizer_verified":
            e.verification_label = "details_reviewed"
    db.commit()
    feedcache.invalidate_all()
    if verified and not was_verified:
        org_alerts.verification_result(db, org, True)


@router.get("/organizers")
def organizers(q: str = Query("", max_length=100), user: User = Depends(admin_only), db: Session = Depends(get_db)):
    from sqlalchemy import func

    counts = dict(db.execute(select(Event.organizer_id, func.count()).where(Event.status == "published").group_by(Event.organizer_id)).all())
    stmt = select(Organizer, User).join(User, User.id == Organizer.user_id)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Organizer.org_name).like(like), func.lower(User.email).like(like),
                              func.lower(func.coalesce(Organizer.college_or_company, "")).like(like)))
    rows = db.execute(stmt.order_by(Organizer.org_name).limit(200)).all()
    # Unverified first: they're the ones an admin is usually looking for.
    rows.sort(key=lambda r: (r[0].trust_level != "new", r[0].org_name.lower()))
    return {"items": [{"id": o.id, "name": o.org_name, "slug": o.slug, "email": u.email, "college_or_company": o.college_or_company,
                       "city": o.city, "trust_level": o.trust_level, "events": counts.get(o.id, 0), "joined": iso_utc(u.created_at)}
                      for o, u in rows]}


@router.post("/organizers/{organizer_id}/trust")
def change_trust(organizer_id: str, body: TrustIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    org = db.get(Organizer, organizer_id)
    if org is None:
        raise HTTPException(404, "That organizer doesn't exist.")
    set_trust(db, org, body.level, user)
    return {"id": org.id, "trust_level": org.trust_level}
