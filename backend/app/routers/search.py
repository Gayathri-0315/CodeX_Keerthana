"""Natural-language search (prompt v2, item 19). Open to guests; students also get the "Fits your time" badge."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import RateLimit, client_ip, optional_user
from ..models import User
from ..services import search
from ..services.explore import apply_filters
from ..timeutil import ist_today

router = APIRouter(prefix="/search", tags=["search"])

ip_limit = RateLimit(30, 60, "You're searching quickly. Wait a moment and try again.")
user_limit = RateLimit(20, 60, "You're searching quickly. Wait a moment and try again.")


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=search.MAX_TEXT)


class ResultsIn(BaseModel):
    filters: search.SearchFilters
    limit: int = Field(20, ge=1, le=50)


def _limit(request: Request, user: User | None) -> None:
    ip_limit.hit(client_ip(request))
    if user is not None:
        user_limit.hit(user.id)


def chips(f: search.SearchFilters) -> list[dict]:
    """What the search understood, as removable chips. `field` says what removing it clears."""
    from ..services.categories import CATEGORIES

    names = {s: n for s, n, _ in CATEGORIES}
    out = [{"field": "categories", "value": c, "label": names[c]} for c in f.categories]
    if f.event_type:
        out.append({"field": "event_type", "value": f.event_type, "label": f.event_type.capitalize() + "s"})
    if f.when:
        out.append({"field": "when", "value": f.when, "label": search.when_label(f.when)})
    elif f.date_from or f.date_to:
        a, b = f.date_from, f.date_to
        label = f"{a:%d %b}" if a == b else f"{a:%d %b} to {b:%d %b}" if a and b else f"From {a:%d %b}" if a else f"Until {b:%d %b}"
        out.append({"field": "when", "value": None, "label": label})
    if f.time_of_day:
        out.append({"field": "time_of_day", "value": f.time_of_day, "label": f.time_of_day.capitalize()})
    if f.free_only:
        out.append({"field": "free_only", "value": True, "label": "Free"})
    if f.max_fee_inr is not None:
        out.append({"field": "max_fee_inr", "value": f.max_fee_inr, "label": f"Up to ₹{f.max_fee_inr}"})
    if f.mode:
        out.append({"field": "mode", "value": f.mode, "label": "Online" if f.mode == "online" else "In person"})
    if f.max_distance_km is not None:
        out.append({"field": "max_distance_km", "value": f.max_distance_km, "label": f"Within {f.max_distance_km} km"})
    for k in f.keywords:
        out.append({"field": "keywords", "value": k, "label": f'"{k}"'})
    return out


@router.post("/parse")
def parse(body: ParseIn, request: Request, user: User | None = Depends(optional_user)):
    _limit(request, user)
    f, source = search.parse(body.text, ist_today())
    return {"filters": f.model_dump(mode="json"), "chips": chips(f), "source": source}


@router.post("/results")
def results(body: ResultsIn, request: Request, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    """Events for these filters. Nothing found -> loosen one filter at a time and say what changed."""
    _limit(request, user)
    student = user is not None and user.role == "student"
    if student:
        from ..services.feed import evaluate

        data = evaluate(db, user)
    else:
        from .public import guest_data

        data = guest_data(db)
    f = body.filters
    if f.when:  # dates are always the server's, from the date word
        f = search.finish(f, ist_today())
    items = apply_filters(data, search.to_filters(f))
    relaxed = None
    if not items and not f.is_empty():
        changes: list[str] = []
        for loose, change in search.relaxations(f):
            changes.append(change)
            items = apply_filters(data, search.to_filters(loose))
            if items:
                relaxed = {"message": f"Nothing for {search.describe(f)}. Showing {' and '.join(changes)}.",
                           "filters": loose.model_dump(mode="json"), "chips": chips(loose)}
                break
    if student:
        from .feed import page_out

        out = page_out(db, user, data, items, 0, body.limit, badges=True)
    else:
        from .public import guest_card

        page = items[: body.limit]
        out = {"items": [guest_card(data, i) for i in page], "next_cursor": None, "total": len(items)}
    out["relaxed"] = relaxed
    return out
