from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Event, Feedback, SavedEvent, User
from ..seed.venues import AREAS
from ..serializers import event_detail
from ..services import feedcache
from ..services.feed import evaluate_one, registered_counts

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
    return event_detail(ev, registered_counts(db, [event.id]).get(event.id, 0), saved)


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


@router.get("/areas")
def areas(q: str = Query("", max_length=60)):
    q = q.strip().lower()
    return {"areas": [a for a in AREAS if q in a["name"].lower()]}
