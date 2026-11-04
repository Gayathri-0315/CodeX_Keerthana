from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Registration, SavedEvent, User
from ..serializers import event_card, registration_brief
from ..services.explore import Filters, apply_filters, fit_badge
from ..services.feed import evaluate, user_windows
from ..services import together
from ..services.registration import ACTIVE

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
    regs = {r.event_id: registration_brief(r) for r in db.scalars(
        select(Registration).where(Registration.user_id == user.id, Registration.event_id.in_([i.event.id for i in page]),
                                   Registration.status.in_(ACTIVE))
    )}
    classmates = together.classmates_going(db, user, [i.event.id for i in page])
    return {
        "items": [event_card(i, data.counts.get(i.event.id, 0), i.event.id in saved, regs.get(i.event.id), classmates.get(i.event.id))
                  for i in page],
        "next_cursor": str(offset + limit) if offset + limit < len(items) else None,
        "total": len(items),
    }


def page_out(db: Session, user: User, data, items, offset: int, limit: int, badges: bool = False) -> dict:
    saved = saved_ids(db, user)
    page = items[offset : offset + limit]
    regs = {r.event_id: registration_brief(r) for r in db.scalars(
        select(Registration).where(Registration.user_id == user.id, Registration.event_id.in_([i.event.id for i in page]),
                                   Registration.status.in_(ACTIVE))
    )}
    classmates = together.classmates_going(db, user, [i.event.id for i in page])
    windows = user_windows(db, user) if badges else None
    out = []
    for i in page:
        card = event_card(i, data.counts.get(i.event.id, 0), i.event.id in saved, regs.get(i.event.id), classmates.get(i.event.id))
        if badges:
            card["time_fit"] = fit_badge(i, user, windows, data.going)
        out.append(card)
    return {"items": out, "next_cursor": str(offset + limit) if offset + limit < len(items) else None, "total": len(items)}


def parse_cursor(cursor: str | None) -> int:
    try:
        return max(0, int(cursor)) if cursor else 0
    except ValueError:
        raise HTTPException(400, "That page link is invalid. Refresh the list.")


@router.get("/explore")
def explore(
    category: str | None = Query(None, max_length=60),
    date_from: date | None = None,
    date_to: date | None = None,
    price: Literal["free", "paid"] | None = None,
    mode: Literal["online", "in_person"] | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Every upcoming published event, by start date, with a "Fits your time" badge. Nothing is hidden for not fitting."""
    data = evaluate(db, user)
    items = apply_filters(data, Filters(category=category, date_from=date_from, date_to=date_to, price=price, mode=mode, q=q))
    return page_out(db, user, data, items, parse_cursor(cursor), limit, badges=True)


@router.get("/categories")
def categories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Categories that have upcoming events, for the Explore filter."""
    data = evaluate(db, user)
    return {"categories": sorted({i.event.category for i in data.items if i.event.category})}


@router.get("/count")
def feed_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Events that fit the user's free time right now (drives the live calendar pill)."""
    data = evaluate(db, user)
    return {"fits": len(data.for_you()), "almost": len(data.almost())}
