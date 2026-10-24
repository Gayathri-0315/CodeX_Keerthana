from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import SavedEvent, User
from ..serializers import event_card
from ..services.feed import evaluate

router = APIRouter(prefix="/feed", tags=["feed"])


def saved_ids(db: Session, user: User) -> set[str]:
    return set(db.scalars(select(SavedEvent.event_id).where(SavedEvent.user_id == user.id)))


@router.get("")
def feed(
    tab: Literal["for_you", "almost", "saved"] = "for_you",
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    data = evaluate(db, user)
    saved = saved_ids(db, user)
    if tab == "for_you":
        items = data.for_you()
    elif tab == "almost":
        items = data.almost() if user.show_almost else []
    else:
        items = sorted((i for i in data.items if i.event.id in saved), key=lambda i: i.event.start_at)

    try:
        offset = int(cursor) if cursor else 0
    except ValueError:
        raise HTTPException(400, "That page link is invalid. Refresh the feed.")
    page = items[offset : offset + limit]
    return {
        "items": [event_card(i, data.counts.get(i.event.id, 0), i.event.id in saved) for i in page],
        "next_cursor": str(offset + limit) if offset + limit < len(items) else None,
        "total": len(items),
    }


@router.get("/count")
def feed_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Events that fit the user's free time right now (drives the live calendar pill)."""
    data = evaluate(db, user)
    return {"fits": len(data.for_you()), "almost": len(data.almost())}
