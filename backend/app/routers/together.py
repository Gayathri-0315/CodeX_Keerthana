"""'Go together' invites. Viewing an invite is public (it's a link a friend opens); accepting needs an account."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Event, Registration, User
from ..services import registration, together
from ..timeutil import DAY_NAMES, to_ist

router = APIRouter(tags=["together"])


@router.post("/registrations/{reg_id}/invite")
def create_invite(reg_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    reg = db.get(Registration, reg_id)
    if reg is None or reg.user_id != user.id:
        raise HTTPException(404, "That registration doesn't exist.")
    inv = together.create_invite(db, reg)
    return {"code": inv.code, "url": together.invite_url(inv.code)}


@router.get("/invites/{code}")
def get_invite(code: str, db: Session = Depends(get_db)):
    return together.invite_info(db, code)


@router.post("/invites/{code}/accept")
def accept_invite(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "student":
        raise HTTPException(403, "Only students can join events.")
    reg = together.accept(db, user, code)
    out = registration.registration_out(db, reg, user)
    names = [c["name"] for c in out["companions"]]
    day = DAY_NAMES[to_ist(db.get(Event, reg.event_id).start_at).weekday()]
    if reg.status == "waitlisted":
        toast = {"title": "You're on the list", "body": f"It's full, so you're #{reg.waitlist_position}. {together.names_text(names)} knows you're trying."}
    else:
        toast = {"title": f"You're going with {together.names_text(names)}", "body": f"See you {day}. Your passes are linked."}
    return {**out, "toast": toast}
