"""Event group chat endpoints. Only the host and confirmed attendees can read or post."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import ChatMessage, ChatRemoval, ChatReport, Event, Registration, User
from ..services import chat
from ..timeutil import iso_utc

router = APIRouter(tags=["chat"])


class PostIn(BaseModel):
    body: str = Field(min_length=1, max_length=chat.MAX_LEN * 4)  # the service gives the friendly "too long" message
    announcement: bool = False


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class LockIn(BaseModel):
    locked: bool


def _message(db: Session, user: User, message_id: str) -> tuple[ChatMessage, Event]:
    m = db.get(ChatMessage, message_id)
    if m is None:
        raise HTTPException(404, "That message doesn't exist.")
    return m, chat.get_event_for(db, user, m.event_id)


@router.get("/events/{event_id}/chat")
def read_chat(event_id: str, limit: int = Query(100, ge=1, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = chat.get_event_for(db, user, event_id)
    rows = db.execute(
        select(ChatMessage, User).join(User, User.id == ChatMessage.sender_id)
        .where(ChatMessage.event_id == event.id).order_by(ChatMessage.created_at.desc()).limit(limit)
    ).all()
    rows.reverse()
    pinned = next((m for m, _ in rows if m.pinned and not m.hidden_reason), None)
    if pinned is None:
        p = db.execute(select(ChatMessage, User).join(User, User.id == ChatMessage.sender_id).where(
            ChatMessage.event_id == event.id, ChatMessage.pinned.is_(True), ChatMessage.hidden_reason.is_(None))).first()
        pinned = p[0] if p else None
        pinned_sender = p[1] if p else None
    else:
        pinned_sender = next(u for m, u in rows if m.id == pinned.id)
    host = chat.is_host(user, event)
    chat.mark_read(db, user, event)
    return {
        "event": {"id": event.id, "title": event.title, "start_at": iso_utc(event.start_at)},
        "role": "host" if host else "member",
        "locked": event.chat_locked,
        "read_only": chat.read_only(event),
        "can_post": not chat.read_only(event) and (host or not event.chat_locked),
        "members": len(chat.member_ids(db, event)),
        "pinned": chat.message_out(pinned, pinned_sender, user, event) if pinned else None,
        "messages": [chat.message_out(m, u, user, event) for m, u in rows],
    }


@router.post("/events/{event_id}/chat", status_code=201)
def send(event_id: str, body: PostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = chat.get_event_for(db, user, event_id)
    m = chat.post(db, user, event, body.body, body.announcement)
    return chat.message_out(m, user, user, event)


@router.delete("/chat/messages/{message_id}", status_code=204)
def delete_message(message_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m, event = _message(db, user, message_id)
    if m.sender_id != user.id and not chat.is_host(user, event):
        raise HTTPException(403, "You can only remove your own messages.")
    m.hidden_reason = "Removed by the sender" if m.sender_id == user.id else "Removed by the host"
    m.pinned = False
    db.commit()
    chat.broadcast(db, event, {"type": "update", "event_id": event.id})


@router.post("/chat/messages/{message_id}/pin")
def pin(message_id: str, pinned: bool = True, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m, event = _message(db, user, message_id)
    if not chat.is_host(user, event):
        raise HTTPException(403, "Only the host can pin messages.")
    for other in db.scalars(select(ChatMessage).where(ChatMessage.event_id == event.id, ChatMessage.pinned.is_(True))):
        other.pinned = False
    m.pinned = pinned and not m.hidden_reason
    db.commit()
    chat.broadcast(db, event, {"type": "update", "event_id": event.id})
    return {"pinned": m.pinned}


@router.post("/chat/messages/{message_id}/report", status_code=204)
def report(message_id: str, body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m, _ = _message(db, user, message_id)
    if m.sender_id == user.id:
        raise HTTPException(409, "You can't report your own message.")
    db.add(ChatReport(message_id=m.id, reporter_id=user.id, reason=body.reason.strip()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # already reported by this person


@router.post("/events/{event_id}/chat/lock")
def lock(event_id: str, body: LockIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = chat.get_event_for(db, user, event_id)
    if not chat.is_host(user, event):
        raise HTTPException(403, "Only the host can change who posts.")
    event.chat_locked = body.locked
    db.commit()
    chat.broadcast(db, event, {"type": "update", "event_id": event.id})
    return {"locked": event.chat_locked}


@router.get("/events/{event_id}/chat/members")
def members(event_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Host only: first names, so the host can remove someone. Students see only the count."""
    event = chat.get_event_for(db, user, event_id)
    if not chat.is_host(user, event):
        raise HTTPException(403, "Only the host can see the member list.")
    people = [db.get(User, uid) for uid in chat.member_ids(db, event) if uid != user.id]
    return {"items": [{"id": p.id, "name": p.name} for p in people if p]}


@router.post("/events/{event_id}/chat/remove/{member_id}", status_code=204)
def remove_member(event_id: str, member_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    event = chat.get_event_for(db, user, event_id)
    if not chat.is_host(user, event) or member_id == user.id:
        raise HTTPException(403, "Only the host can remove members.")
    if not db.get(ChatRemoval, (event.id, member_id)):
        db.add(ChatRemoval(event_id=event.id, user_id=member_id))
        db.commit()
    chat.broadcast(db, event, {"type": "update", "event_id": event.id})


@router.get("/me/chats")
def my_chats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Chats I'm in, with unread counts (for the Chat buttons)."""
    if user.organizer is not None:
        events = db.scalars(select(Event).where(Event.organizer_id == user.organizer.id, Event.status == "published")).unique().all()
    else:
        events = db.scalars(select(Event).join(Registration, Registration.event_id == Event.id).where(
            Registration.user_id == user.id, Registration.status.in_(chat.MEMBER_STATUSES))).unique().all()
    return {"items": [{"event_id": e.id, "unread": chat.unread(db, user, e.id)} for e in events if chat.is_member(db, user, e)]}
