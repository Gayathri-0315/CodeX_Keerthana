from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import AvailabilitySlot, Feedback, Notification, Registration, SavedAlert, SavedEvent, User, UserInterest
from ..schemas import InterestsPut, OrganizerOut, UserOut, UserPatch
from ..security import COOKIE_NAME
from ..services import feedcache

router = APIRouter(prefix="/users", tags=["users"])


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.email_verified = user.email_verified_at is not None
    out.organizer = OrganizerOut.model_validate(user.organizer) if user.organizer else None
    return out


@router.patch("/me", response_model=UserOut)
def patch_me(body: UserPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    feedcache.invalidate(user.id)
    return user_out(user)


@router.put("/me/interests", response_model=UserOut)
def put_interests(body: InterestsPut, user: User = Depends(current_user), db: Session = Depends(get_db)):
    seen: dict[str, int] = {}
    for i in body.interests:
        seen[i.tag.strip().lower()] = i.weight
    user.interests = [UserInterest(tag=t, weight=w) for t, w in seen.items()]
    if body.interest_text is not None:
        user.interest_text = body.interest_text.strip()
    db.commit()
    feedcache.invalidate(user.id)
    return user_out(user)


@router.get("/me/export")
def export_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    def rows(model):
        cols = [c.name for c in model.__table__.columns]
        return [
            {c: getattr(r, c) for c in cols}
            for r in db.scalars(select(model).where(model.user_id == user.id))
        ]

    profile = user_out(user).model_dump()
    return {
        "profile": profile,
        "availability": rows(AvailabilitySlot),
        "registrations": rows(Registration),
        "saved": rows(SavedEvent),
        "feedback": rows(Feedback),
        "notifications": rows(Notification),
        "saved_alerts": rows(SavedAlert),
    }


@router.delete("/me", status_code=204)
def delete_me(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    feedcache.invalidate(user.id)
    response.delete_cookie(COOKIE_NAME)
