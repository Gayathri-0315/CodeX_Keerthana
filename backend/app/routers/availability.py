from collections import defaultdict

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user, upload_limit
from ..models import AvailabilitySlot, User
from ..schemas import AvailabilityOut, AvailabilityPut
from ..services import feedcache
from ..services.extraction import extract_timetable
from ..services.scheduling import gaps_from_periods
from ..services.uploads import read_upload

router = APIRouter(prefix="/availability", tags=["availability"])


def _list(db: Session, user: User) -> AvailabilityOut:
    slots = db.scalars(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.user_id == user.id)
        .order_by(AvailabilitySlot.date.is_not(None), AvailabilitySlot.day_of_week, AvailabilitySlot.start_min)
    ).all()
    return AvailabilityOut.model_validate({"slots": slots}, from_attributes=True)


DAY_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


@router.post("/timetable", dependencies=[Depends(upload_limit)])
def import_timetable(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Timetable photo -> class periods -> free gaps (SPEC 5.1, 6.1). Nothing is saved: the student reviews first."""
    upload = read_upload(file.file.read(), file.filename or "timetable")
    result = extract_timetable(db, upload)
    periods: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for p in result["timetable"]["periods"]:
        s, e = _minutes(p["start"]), _minutes(p["end"])
        if e > s:
            periods[DAY_INDEX[p["day"]]].append((s, e))
    found = bool(periods)
    gaps = gaps_from_periods(periods, settings.timetable_day_start_min, settings.timetable_day_end_min) if found else {}
    return {
        **result,
        "free_slots": [{"day_of_week": d, "start_min": s, "end_min": e} for d, spans in sorted(gaps.items()) for s, e in spans],
        "day_start_min": settings.timetable_day_start_min,
        "day_end_min": settings.timetable_day_end_min,
    }


@router.get("/samples")
def timetable_samples(user: User = Depends(current_user)):
    if not settings.is_dev:  # sample timetables are a local-development aid only
        return {"timetables": []}
    from ..seed.make_samples import sample_timetables

    return {"timetables": [{**s, "url": f"/api/samples/timetables/{s['name']}.png"} for s in sample_timetables()]}


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


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
