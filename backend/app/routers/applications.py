"""Applying for an internship on ShowUp, when the organizer didn't give an outside apply link.

Students send a short note (and optionally a portfolio or resume link). The organizer gets an alert and sees
applicants with their email so they can reply. Students can withdraw while the internship is open.
"""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import RateLimit, require_role
from ..models import Application, Event, User
from ..timeutil import iso_utc, utcnow

router = APIRouter(tags=["applications"])
student_only = require_role("student")
organizer_only = require_role("organizer")
apply_limit = RateLimit(10, 60, "Wait a moment before sending more applications.")


class ApplyIn(BaseModel):
    note: str = Field(min_length=20, max_length=1000)
    link: str | None = Field(None, max_length=500)

    @field_validator("note")
    @classmethod
    def _note(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Write at least a sentence about why you're interested")
        return v

    @field_validator("link")
    @classmethod
    def _link(cls, v: str | None) -> str | None:
        v = (v or "").strip() or None
        if v and (urlparse(v).scheme not in ("http", "https") or not urlparse(v).hostname):
            raise ValueError("Use a full link starting with https://")
        return v


def takes_applications(event: Event) -> bool:
    return event.event_type == "internship" and not event.registration_url


def application_out(a: Application | None) -> dict | None:
    return {"id": a.id, "status": a.status, "at": iso_utc(a.created_at)} if a else None


def _open_internship(db: Session, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.status != "published":
        raise HTTPException(404, "This internship isn't available.")
    if not takes_applications(event):
        raise HTTPException(409, "Apply on the organizer's own site, using the Apply button.")
    return event


@router.post("/events/{event_id}/apply", status_code=201)
def apply(event_id: str, body: ApplyIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    from ..services import org_alerts

    apply_limit.hit(user.id)
    event = _open_internship(db, event_id)
    if event.start_at < utcnow():
        raise HTTPException(409, "Applications for this internship have closed.")
    a = Application(event_id=event.id, user_id=user.id, note=body.note, link=body.link)
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You've already applied for this internship.")
    first = (user.name or "A student").split(" ")[0]
    org_alerts.alert(db, event, "org_registration", "New application", f"{first} applied for {org_alerts._short(event.title)}.")
    return application_out(a)


@router.delete("/events/{event_id}/apply", status_code=204)
def withdraw(event_id: str, user: User = Depends(student_only), db: Session = Depends(get_db)):
    a = db.scalar(select(Application).where(Application.event_id == event_id, Application.user_id == user.id))
    if a is None:
        raise HTTPException(404, "You haven't applied for this internship.")
    db.delete(a)
    db.commit()


@router.get("/organizer/events/{event_id}/applications")
def applications(event_id: str, user: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """The organizer's applicants, newest first, with their email so they can reply."""
    event = db.get(Event, event_id)
    if event is None or user.organizer is None or event.organizer_id != user.organizer.id:
        raise HTTPException(404, "That event doesn't exist.")
    rows = db.execute(select(Application, User).join(User, User.id == Application.user_id)
                      .where(Application.event_id == event.id).order_by(Application.created_at.desc())).all()
    return {"items": [{"id": a.id, "name": u.name, "email": u.email, "college": u.college, "note": a.note, "link": a.link,
                       "status": a.status, "at": iso_utc(a.created_at)} for a, u in rows]}
