"""Event group chat: the host (the event's organizer) and confirmed attendees.

Members: registered or checked-in students (including accepted "Go together" invites), never the
waitlist, minus anyone the host removed. First names only; emails and phones never shown. The chat
turns read-only a few days after the event ends.
"""

import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ChatMessage, ChatRead, ChatRemoval, Event, Registration, User
from ..timeutil import iso_utc, utcnow
from . import stream

MEMBER_STATUSES = ("registered", "attended")
READ_ONLY_AFTER = timedelta(days=3)
MAX_LEN = 1000
RATE = (8, 60)  # messages per seconds, per person per chat
NEW_ACCOUNT = timedelta(days=7)
LINK = re.compile(r"https?://|www\.|\b[\w-]+\.(com|in|org|net|io|ly|me|link|xyz|app)\b", re.I)

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def first_name(u: User) -> str:
    return (u.name or "Someone").split(" ")[0]


def is_host(user: User, event: Event) -> bool:
    return user.organizer is not None and event.organizer_id == user.organizer.id


def is_member(db: Session, user: User, event: Event) -> bool:
    if is_host(user, event):
        return True
    if user.role != "student":
        return False
    if db.get(ChatRemoval, (event.id, user.id)):
        return False
    return db.scalar(select(Registration.id).where(Registration.event_id == event.id, Registration.user_id == user.id,
                                                   Registration.status.in_(MEMBER_STATUSES)).limit(1)) is not None


def member_ids(db: Session, event: Event) -> list[str]:
    removed = set(db.scalars(select(ChatRemoval.user_id).where(ChatRemoval.event_id == event.id)))
    ids = [u for u in db.scalars(select(Registration.user_id).where(Registration.event_id == event.id,
                                                                   Registration.status.in_(MEMBER_STATUSES))) if u not in removed]
    if event.organizer is not None:
        ids.append(event.organizer.user_id)
    return list(dict.fromkeys(ids))


def read_only(event: Event, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return event.status == "cancelled" or (event.end_at is not None and now > event.end_at + READ_ONLY_AFTER)


def get_event_for(db: Session, user: User, event_id: str) -> Event:
    event = db.get(Event, event_id)
    if event is None or not is_member(db, user, event):
        # Same answer whether the event exists or you're just not in it.
        raise HTTPException(404, "This chat is for the host and people going to the event.")
    return event


def message_out(m: ChatMessage, sender: User, me: User, event: Event) -> dict:
    host = event.organizer is not None and sender.id == event.organizer.user_id
    return {
        "id": m.id,
        "body": m.body if not m.hidden_reason else None,
        "hidden": bool(m.hidden_reason),
        "announcement": m.announcement,
        "pinned": m.pinned,
        "created_at": iso_utc(m.created_at),
        "sender": {"id": sender.id, "name": event.organizer.org_name if host else first_name(sender), "is_host": host, "is_me": sender.id == me.id},
    }


def check_rate(user: User, event: Event) -> None:
    q = _hits[(user.id, event.id)]
    now = time.monotonic()
    while q and now - q[0] > RATE[1]:
        q.popleft()
    if len(q) >= RATE[0]:
        raise HTTPException(429, "You're sending messages quickly. Wait a moment and try again.")
    q.append(now)


def rule_check(text: str, user: User, host: bool) -> str | None:
    """Reasons a message can't be posted, from simple rules (the AI safety check adds to this)."""
    from .spam import PAY_WORDS, PHONE, QR_PAY, SCAM_PHRASES, SHORTENERS, UPI_ID

    low = text.lower()
    if UPI_ID.search(text) or QR_PAY.search(text) or (PHONE.search(text) and PAY_WORDS.search(text)):
        return "Payment requests aren't allowed in event chats."
    if any(re.search(rf"\b{re.escape(p)}\b", low) for p in SCAM_PHRASES):
        return "That message looks like a scam, so it wasn't posted."
    if any(s in low for s in SHORTENERS):
        return "Short links aren't allowed. Share the full link."
    if not host and LINK.search(text) and utcnow() - user.created_at < NEW_ACCOUNT:
        return "New accounts can't share links yet."
    if not host and PHONE.search(text):
        return "For your safety, phone numbers aren't shared in group chats."
    return None


def post(db: Session, user: User, event: Event, body: str, announcement: bool = False) -> ChatMessage:
    from . import moderation

    text = body.strip()
    if not text:
        raise HTTPException(422, "Write a message first.")
    if len(text) > MAX_LEN:
        raise HTTPException(422, f"Keep messages under {MAX_LEN} characters.")
    host = is_host(user, event)
    if read_only(event):
        raise HTTPException(409, "This chat is closed now that the event is over.")
    if event.chat_locked and not host:
        raise HTTPException(403, "Only the host can post in this chat right now.")
    if announcement and not host:
        raise HTTPException(403, "Only the host can post announcements.")
    check_rate(user, event)
    if reason := rule_check(text, user, host):
        raise HTTPException(422, reason)
    if reason := moderation.check_message(text):
        raise HTTPException(422, reason)
    m = ChatMessage(event_id=event.id, sender_id=user.id, body=text, announcement=announcement)
    db.add(m)
    db.commit()
    mark_read(db, user, event)
    broadcast(db, event, {"type": "message", "event_id": event.id, "message_id": m.id})
    if announcement:
        announce(db, event, user, text)
    return m


def announce(db: Session, event: Event, host_user: User, text: str) -> None:
    """Announcements also reach members as an alert; ordinary messages only raise the unread count."""
    from . import notify

    for uid in member_ids(db, event):
        if uid == host_user.id:
            continue
        member = db.get(User, uid)
        n = notify.Notification(user_id=uid, type="chat_announcement", event_id=event.id,
                                title=notify._fit(f"{notify._short(event.organizer.org_name, 30)}: announcement"),
                                body=notify._fit(text), payload={"path": f"/event/{event.id}/chat"})
        db.add(n)
        db.commit()
        notify.deliver(db, n, member)


def broadcast(db: Session, event: Event, data: dict) -> None:
    for uid in member_ids(db, event):
        stream.publish(uid, "chat", data)


def mark_read(db: Session, user: User, event: Event) -> None:
    row = db.get(ChatRead, (event.id, user.id))
    if row:
        row.last_read_at = utcnow()
    else:
        db.add(ChatRead(event_id=event.id, user_id=user.id, last_read_at=utcnow()))
    db.commit()


def unread(db: Session, user: User, event_id: str) -> int:
    row = db.get(ChatRead, (event_id, user.id))
    q = select(func.count()).select_from(ChatMessage).where(ChatMessage.event_id == event_id, ChatMessage.sender_id != user.id,
                                                            ChatMessage.hidden_reason.is_(None))
    if row:
        q = q.where(ChatMessage.created_at > row.last_read_at)
    return db.scalar(q) or 0
