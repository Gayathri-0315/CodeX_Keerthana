"""Organizer profile settings: profile (group 1), trust and verification (group 2), notifications (group 3),
and a readable "Download my data" document."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role, upload_limit
from ..models import Event, Organizer, OrgVerificationRequest, Registration, StoredFile, User
from ..services import feedcache, org_alerts
from ..services.uploads import public_url, read_upload, store_image
from ..timeutil import iso_utc, to_ist, utcnow

router = APIRouter(prefix="/organizer/profile", tags=["organizer profile"])
organizer_only = require_role("organizer")

ORG_TYPES = ("college_club", "department", "company", "community", "independent")
TRUST_LABELS = {"new": "New", "verified": "Verified", "trusted": "Trusted"}
SEAT_STATUSES = ("registered", "promoted_pending", "attended")


def my_org(user: User) -> Organizer:
    if user.organizer is None:
        raise HTTPException(403, "This account isn't set up as an organizer.")
    return user.organizer


def _https(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    v = v.strip()
    if not re.match(r"^https://[^\s]+\.[^\s]+$", v):
        raise ValueError("Use a full link starting with https://")
    return v


class ProfileIn(BaseModel):
    org_name: str | None = Field(None, min_length=2, max_length=160)
    org_type: Literal["college_club", "department", "company", "community", "independent"] | None = None
    college_or_company: str | None = Field(None, max_length=160)
    city: str | None = Field(None, max_length=80)
    bio: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=32, pattern=r"^[0-9+()\- ]*$")
    website: str | None = Field(None, max_length=300)
    instagram: str | None = Field(None, max_length=300)
    linkedin: str | None = Field(None, max_length=300)
    show_official_email: bool | None = None
    faculty_name: str | None = Field(None, max_length=120)
    faculty_email: EmailStr | None = None
    notif_prefs: dict[str, bool] | None = None
    daily_digest: bool | None = None

    _links = field_validator("website", "instagram", "linkedin")(classmethod(lambda cls, v: _https(v)))

    @field_validator("notif_prefs")
    @classmethod
    def _known(cls, v):
        if v is not None and not set(v) <= set(org_alerts.PREFS):
            raise ValueError("Unknown alert type.")
        return v


def track_record(db: Session, org: Organizer) -> dict:
    """Computed by the app, never editable."""
    hosted = db.scalar(select(func.count()).select_from(Event).where(
        Event.organizer_id == org.id, Event.status == "published", Event.end_at < utcnow())) or 0
    return {
        "events_hosted": max(hosted, org.past_events_count or 0),
        "attendance_rate": org.avg_attendance_rate,
        "response_time_hours": None,  # filled in once students can message organizers
    }


def profile_out(db: Session, user: User, org: Organizer) -> dict:
    pending = db.scalar(select(OrgVerificationRequest).where(OrgVerificationRequest.organizer_id == org.id)
                        .order_by(OrgVerificationRequest.created_at.desc()).limit(1))
    return {
        "org_name": org.org_name, "org_type": org.org_type, "college_or_company": org.college_or_company, "city": org.city,
        "bio": org.bio, "logo_url": org.logo_url, "phone": org.phone, "website": org.website, "instagram": org.instagram,
        "linkedin": org.linkedin, "show_official_email": org.show_official_email,
        "official_email": user.email, "email_domain": org.org_email_domain,
        "trust_level": org.trust_level, "trust_label": TRUST_LABELS.get(org.trust_level, org.trust_level),
        "faculty_name": org.faculty_name, "faculty_email": org.faculty_email,
        "verification": {"status": pending.status, "submitted_at": iso_utc(pending.created_at),
                         "document_type": pending.document_type} if pending else None,
        "track_record": track_record(db, org),
        "notif_prefs": org_alerts.prefs_of(org), "daily_digest": org.daily_digest,
    }


@router.get("")
def get_profile(user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    return profile_out(db, user, my_org(user))


@router.patch("")
def patch_profile(body: ProfileIn, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    org = my_org(user)
    data = body.model_dump(exclude_unset=True)
    if "notif_prefs" in data and data["notif_prefs"] is not None:
        data["notif_prefs"] = {**org_alerts.prefs_of(org), **data["notif_prefs"]}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        if key == "org_name" and not value:
            continue
        setattr(org, key, value)
    db.commit()
    feedcache.invalidate_all()  # organizer name and label appear on cards
    return profile_out(db, user, org)


@router.post("/logo", dependencies=[Depends(upload_limit)])
def upload_logo(file: UploadFile = File(...), user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    org = my_org(user)
    upload = read_upload(file.file.read(), file.filename or "logo")
    if upload.clean is None:
        raise HTTPException(415, "Upload the logo as an image (PNG, JPEG or WebP).")
    org.logo_url = public_url(store_image(db, upload))
    db.commit()
    feedcache.invalidate_all()
    return profile_out(db, user, org)


@router.delete("/logo")
def remove_logo(user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    org = my_org(user)
    org.logo_url = None
    db.commit()
    return profile_out(db, user, org)


@router.post("/verification", dependencies=[Depends(upload_limit)])
def request_verification(
    document_type: Literal["college_id", "faculty_letter", "company_proof", "other"] = Form(...),
    note: str = Form("", max_length=500),
    file: UploadFile = File(...),
    user: User = Depends(organizer_only),
    db: Session = Depends(get_db),
):
    """Send a document to admin review. Kept private: only admins can open it."""
    org = my_org(user)
    if org.trust_level in ("verified", "trusted"):
        raise HTTPException(409, "Your organization is already verified.")
    if db.scalar(select(OrgVerificationRequest.id).where(OrgVerificationRequest.organizer_id == org.id,
                                                         OrgVerificationRequest.status == "pending")):
        raise HTTPException(409, "Your request is already with our team. We'll let you know the result.")
    upload = read_upload(file.file.read(), file.filename or "document")
    # Private name (not *.webp), so the public /api/files route never serves it.
    import uuid

    name = f"doc_{uuid.uuid4().hex}"
    data, kind = (upload.clean, "image/webp") if upload.clean else (upload.data, upload.media_type)
    db.add(StoredFile(name=name, content_type=kind, data=data))
    db.add(OrgVerificationRequest(organizer_id=org.id, document_name=name, document_type=document_type, note=note.strip()))
    db.commit()
    return profile_out(db, user, org)


@router.get("/export")
def export_document(user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """'Download my data' as a plain, readable document (not JSON)."""
    org = my_org(user)
    t = track_record(db, org)
    rate = f"{round(t['attendance_rate'] * 100)}%" if t["attendance_rate"] is not None else "not enough events yet"
    lines = [
        "ShowUp: your organizer data",
        f"Prepared on {to_ist(utcnow()).strftime('%d %B %Y, %I:%M %p')} (IST)",
        "",
        "ACCOUNT",
        f"  Name: {user.name}",
        f"  Official email: {user.email}",
        f"  Phone: {org.phone or 'not given'}",
        f"  Account created: {to_ist(user.created_at).strftime('%d %B %Y')}",
        "",
        "ORGANIZATION",
        f"  Name: {org.org_name}",
        f"  Type: {(org.org_type or 'not set').replace('_', ' ')}",
        f"  College or company: {org.college_or_company or 'not set'}",
        f"  City: {org.city or 'not set'}",
        f"  About: {org.bio or 'not set'}",
        f"  Website: {org.website or 'not set'}",
        f"  Instagram: {org.instagram or 'not set'}",
        f"  LinkedIn: {org.linkedin or 'not set'}",
        f"  Show official email on public pages: {'yes' if org.show_official_email else 'no'}",
        f"  Faculty coordinator: {org.faculty_name or 'not set'}{f' ({org.faculty_email})' if org.faculty_email else ''}",
        "",
        "TRUST",
        f"  Status: {TRUST_LABELS.get(org.trust_level, org.trust_level)}",
        f"  Events hosted: {t['events_hosted']}",
        f"  Average attendance: {rate}",
        "",
        "EVENTS",
    ]
    events = db.scalars(select(Event).where(Event.organizer_id == org.id).order_by(Event.start_at.desc())).unique().all()
    if not events:
        lines.append("  No events yet.")
    for e in events:
        seats = db.scalar(select(func.count()).select_from(Registration).where(
            Registration.event_id == e.id, Registration.status.in_(SEAT_STATUSES))) or 0
        when = to_ist(e.start_at).strftime("%d %b %Y, %I:%M %p") if e.start_at else "no date"
        lines += [f"  - {e.title}", f"    When: {when}   Status: {e.status.replace('_', ' ')}   Registered: {seats}", ""]
    lines += ["", "Student details are not included: they belong to the students who registered."]
    text = "\n".join(lines) + "\n"
    filename = f"showup-{re.sub(r'[^a-z0-9]+', '-', org.org_name.lower()).strip('-') or 'organizer'}-data.txt"
    return Response(text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
