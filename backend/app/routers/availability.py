from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import AvailabilitySlot, User
from ..schemas import AvailabilityOut, AvailabilityPut
from ..services import feedcache

router = APIRouter(prefix="/availability", tags=["availability"])


def _list(db: Session, user: User) -> AvailabilityOut:
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.user_id == user.id)
        .order_by(AvailabilitySlot.date.is_not(None), AvailabilitySlot.day_of_week, AvailabilitySlot.start_min)
    ).all()
    return AvailabilityOut.model_validate({"slots": slots}, from_attributes=True)


@router.get("", response_model=AvailabilityOut)
def get_availability(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _list(db, user)


@router.put("", response_model=AvailabilityOut)
def put_availability(body: AvailabilityPut, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Replaces the user's whole slot set in one batched write."""
    db.execute(delete(AvailabilitySlot).where(AvailabilitySlot.user_id == user.id))
    for s in body.slots:
        data = s.model_dump()
        if s.date is not None:
            data["recurring"] = False
            data["day_of_week"] = s.date.weekday()
        else:
            data["recurring"] = True
        db.add(AvailabilitySlot(user_id=user.id, **data))
    db.commit()
    feedcache.invalidate(user.id)
    return _list(db, user)
