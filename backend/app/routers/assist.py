"""Ask about an event: answers only from the event's own details (see services/assist.py)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import RateLimit, client_ip, optional_user
from ..models import Event, User
from ..services import assist, chat

router = APIRouter(tags=["assist"])
ask_limit = RateLimit(15, 60, "You're asking quickly. Wait a moment and try again.")


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=200)


@router.post("/events/{event_id}/ask")
def ask(event_id: str, body: AskIn, request: Request, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    ask_limit.hit(user.id if user else client_ip(request))
    event = db.get(Event, event_id)
    if event is None or event.status != "published":
        raise HTTPException(404, "This event isn't available.")
    out = assist.answer(db, event, body.question)
    # Where to ask when the details don't say: the group chat if you're in it, otherwise the organizer.
    out["ask"] = "chat" if user is not None and chat.is_member(db, user, event) and not chat.read_only(event) else "organizer"
    return out


# ---- writing help for organizers ----

from ..deps import require_role  # noqa: E402

write_limit = RateLimit(10, 60, "Wait a moment before asking for more suggestions.")


class WriteIn(BaseModel):
    title: str = Field("", max_length=200)
    description: str = Field(min_length=20, max_length=4000)


@router.post("/organizer/writing-help")
def writing_help(body: WriteIn, user: User = Depends(require_role("organizer"))):
    """Suggestions only; the organizer chooses what to apply. Nothing is saved."""
    from ..services import writing

    write_limit.hit(user.id)
    return writing.suggest(body.title, body.description)
