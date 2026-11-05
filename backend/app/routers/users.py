from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User, UserInterest
from ..schemas import InterestsPut, OrganizerOut, UserOut, UserPatch
from ..services import feedcache

router = APIRouter(prefix="/users", tags=["users"])


def user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
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
