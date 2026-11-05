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
