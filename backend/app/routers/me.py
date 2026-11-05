"""Personal views for students: their week (feature 1)."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import student_only
from ..models import User
from ..services.week import build_week
from ..timeutil import ist_today

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/week")
def my_week(start: date | None = Query(None, description="Any date; the week starts on its Monday"),
            user: User = Depends(student_only), db: Session = Depends(get_db)):
    day = start or ist_today()
    monday = day - timedelta(days=day.weekday())
    return build_week(db, user, monday)


@router.get("/record")
def my_record(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Private: only the signed-in student's own organizer-confirmed check-ins."""
    from ..services.record import record_out

    return record_out(db, user)


@router.get("/recap")
def my_recap(period: str | None = Query(None, max_length=8, description="e.g. 2026-H2"),
             user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Semester recap: first name only, from organizer check-ins in that half year. Cached 60 s."""
    from fastapi import HTTPException

    from ..services.recap import build_recap

    today = ist_today()
    try:
        return build_recap(db, user, period or f"{today.year}-H{1 if today.month <= 6 else 2}")
    except ValueError as e:
        raise HTTPException(422, str(e))
