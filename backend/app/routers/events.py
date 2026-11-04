from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user, require_verified
from ..models import Event, Feedback, Registration, Report, SavedEvent, User
from ..schemas import ReportIn
from ..seed.venues import AREAS
from ..serializers import event_detail, registration_brief
from ..services import feedcache, ics, notify, registration, together
from ..services.feed import evaluate_one, registered_counts
from ..timeutil import DAY_NAMES, fmt_time, to_ist

router = APIRouter(tags=["events"])


def visible_event(db: Session, event_id: str, user: User) -> Event:
    """Published and cancelled events are public; drafts and flagged ones only to their organizer or admins."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, "That event doesn't exist or was removed.")
    owner = user.organizer is not None and event.organizer_id == user.organizer.id
    if event.status not in ("published", "cancelled") and not owner and user.role != "admin":
        raise HTTPException(404, "That event doesn't exist or was removed.")
    return event


@router.get("/events/{event_id}")
def get_event(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = visible_event(db, event_id, user)
    ev = evaluate_one(db, user, event)
    saved = db.get(SavedEvent, (user.id, event.id)) is not None
    reg = registration.active_registration(db, user.id, event.id)
    out = event_detail(
        ev, registered_counts(db, [event.id]).get(event.id, 0), saved, registration_brief(reg),
        together.classmates_going(db, user, [event.id]).get(event.id),
        together.companions_out(db, reg) if reg else [],
    )
    if reg is None and event.capacity is not None and out["seats_taken"] >= event.capacity:
        waiting = db.scalar(select(func.count()).select_from(Registration).where(
            Registration.event_id == event.id, Registration.status == "waitlisted"))
        out["next_waitlist_position"] = (waiting or 0) + 1
    return out


@router.post("/events/{event_id}/save", status_code=204)
def save_event(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    visible_event(db, event_id, user)
    if db.get(SavedEvent, (user.id, event_id)) is None:
        db.add(SavedEvent(user_id=user.id, event_id=event_id))
        db.commit()


@router.delete("/events/{event_id}/save", status_code=204)
def unsave_event(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(SavedEvent).where(SavedEvent.user_id == user.id, SavedEvent.event_id == event_id))
    db.commit()


@router.post("/events/{event_id}/dismiss", status_code=204)
def dismiss_event(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """"Not for me": hides the event and lowers the weight of its tags for this user."""
    visible_event(db, event_id, user)
    exists = db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.event_id == event_id, Feedback.kind == "not_for_me"))
    if exists is None:
        db.add(Feedback(user_id=user.id, event_id=event_id, kind="not_for_me"))
        db.commit()
    feedcache.invalidate(user.id)


@router.delete("/events/{event_id}/dismiss", status_code=204)
def undo_dismiss(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Feedback).where(Feedback.user_id == user.id, Feedback.event_id == event_id, Feedback.kind == "not_for_me"))
    db.commit()
    feedcache.invalidate(user.id)


class RegisterIn(BaseModel):
    external: bool = False  # "I registered" on the organizer's own site


@router.post("/events/{event_id}/register")
def register(event_id: str, body: RegisterIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """-> registered or waitlisted, with the confirmation copy for the toast."""
    if user.role != "student":
        raise HTTPException(403, "Only students can register for events.")
    require_verified(user)
    event = visible_event(db, event_id, user)
    reg = registration.register(db, user, event, external=bool(body and body.external))
    out = registration.registration_out(db, reg, user)
    start = to_ist(event.start_at)
    day = DAY_NAMES[start.weekday()]
    if reg.status == "waitlisted":
        title, text = "You're on the list", f"You're #{reg.waitlist_position}. We'll ping you if a seat opens."
    else:
        lb = registration.leave_by_for(user, event)
        title = "You're in"
        text = f"See you {day}." + (f" Leave by {fmt_time(to_ist(lb))}." if lb else "")
    notify.create(db, user, "registered" if reg.status != "waitlisted" else "waitlisted", event, title, text, {"registration_id": reg.id})
    return {**out, "toast": {"title": title, "body": text}}


@router.get("/events/{event_id}/ics")
def event_calendar(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = visible_event(db, event_id, user)
    body = ics.event_ics(event, f"{settings.public_url}/event/{event.id}")
    filename = "".join(c if c.isalnum() else "-" for c in event.title.lower()).strip("-")[:40] or "event"
    return Response(body, media_type="text/calendar; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}.ics"'})


REPORTS_TO_HIDE = 3


@router.post("/events/{event_id}/report", status_code=204)
def report_event(event_id: str, body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """One report per person. Three people reporting since the last review hides the event for review."""
    event = visible_event(db, event_id, user)
    if db.scalar(select(Report).where(Report.event_id == event_id, Report.reporter_id == user.id)) is None:
        db.add(Report(event_id=event_id, reporter_id=user.id, reason=body.reason.strip()))
        db.flush()
    q = select(func.count(func.distinct(Report.reporter_id))).where(Report.event_id == event_id)
    if event.reviewed_at:
        q = q.where(Report.created_at > event.reviewed_at)
    if event.status == "published" and db.scalar(q) >= REPORTS_TO_HIDE:
        event.status = "pending_review"
        feedcache.invalidate_all()
    db.commit()


@router.get("/areas")
def areas(q: str = Query("", max_length=60)):
    q = q.strip().lower()
    return {"areas": [a for a in AREAS if q in a["name"].lower()]}
