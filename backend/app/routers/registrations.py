from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Event, Feedback, Registration, User
from ..services import jobs, registration, together
from ..timeutil import utcnow

router = APIRouter(prefix="/registrations", tags=["registrations"])


class FeedbackIn(BaseModel):
    kind: Literal["useful", "as_described", "not_as_described"]


def my_registration(db: Session, user: User, reg_id: str) -> Registration:
    reg = db.get(Registration, reg_id)
    if reg is None or reg.user_id != user.id:
        raise HTTPException(404, "That registration doesn't exist.")
    return reg


@router.get("/me")
def my_registrations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.execute(
        select(Registration, Event).join(Event, Event.id == Registration.event_id)
        .where(Registration.user_id == user.id, Registration.status != "cancelled")
        .order_by(Event.start_at)
    ).unique().all()
    feedback = dict(db.execute(
        select(Feedback.event_id, Feedback.kind).where(Feedback.user_id == user.id, Feedback.kind.in_(("as_described", "not_as_described")))
    ).all())
    upcoming, waitlist, past = [], [], []
    for reg, event in rows:
        out = registration.registration_out(db, reg, user)
        if event.end_at and event.end_at < now or reg.status in ("attended", "no_show"):
            out["feedback"] = feedback.get(event.id)
            past.append(out)
        elif reg.status == "waitlisted":
            waitlist.append(out)
        else:
            upcoming.append(out)
    past.reverse()  # most recent first
    return {"upcoming": upcoming, "waitlist": waitlist, "past": past}


@router.post("/{reg_id}/cancel")
def cancel(reg_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reg = my_registration(db, user, reg_id)
    promoted = registration.cancel(db, reg)
    together.notify_cancel(db, reg)  # friends hear it from ShowUp before the seat moves on
    if promoted:
        jobs.in_background(jobs.offer_seats, promoted)
    return registration.registration_out(db, reg, user)


@router.post("/{reg_id}/confirm-seat")
def confirm_seat(reg_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reg = registration.confirm_seat(db, my_registration(db, user, reg_id))
    return registration.registration_out(db, reg, user)


@router.post("/{reg_id}/confirm-reminder")
def confirm_reminder(reg_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reg = my_registration(db, user, reg_id)
    if reg.status not in ("registered", "promoted_pending"):
        raise HTTPException(409, "This registration is no longer active.")
    reg.reminder_confirmed = True
    reg.showup_likelihood = registration.compute_likelihood(db, user, db.get(Event, reg.event_id), reg).p
    db.commit()
    return registration.registration_out(db, reg, user)


@router.post("/{reg_id}/feedback", status_code=204)
def feedback(reg_id: str, body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reg = my_registration(db, user, reg_id)
    kinds = ("as_described", "not_as_described") if body.kind != "useful" else ("useful",)
    existing = db.scalar(select(Feedback).where(Feedback.user_id == user.id, Feedback.event_id == reg.event_id, Feedback.kind.in_(kinds)))
    if existing:
        existing.kind = body.kind
    else:
        db.add(Feedback(user_id=user.id, event_id=reg.event_id, kind=body.kind))
    db.commit()
