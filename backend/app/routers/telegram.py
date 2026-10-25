"""Telegram linking and the bot's replies to buttons. Without TELEGRAM_BOT_TOKEN everything here is inert."""

import hashlib
import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..deps import current_user
from ..models import Event, Feedback, Registration, TelegramLink, User
from ..services import feedcache, jobs, registration, telegram
from ..timeutil import iso_utc, utcnow

log = logging.getLogger("showup.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"])
CODE_MINUTES = 10


def webhook_secret() -> str:
    return hashlib.sha256(f"showup:{settings.telegram_bot_token}".encode()).hexdigest()[:32]


@router.post("/link-code")
def link_code(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(TelegramLink).where(TelegramLink.user_id == user.id))
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = utcnow() + timedelta(minutes=CODE_MINUTES)
    db.add(TelegramLink(code=code, user_id=user.id, expires_at=expires))
    db.commit()
    return {"enabled": telegram.enabled(), "code": code, "bot_url": telegram.bot_link(code), "expires_at": iso_utc(expires)}


@router.delete("/link", status_code=204)
def unlink(user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.telegram_chat_id = None
    user.notif_channels = {**(user.notif_channels or {}), "telegram": False}
    db.commit()


@router.post("/webhook", status_code=204)
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header("")):
    if not telegram.enabled() or not secrets.compare_digest(x_telegram_bot_api_secret_token, webhook_secret()):
        raise HTTPException(404, "Not found.")
    update = await request.json()
    with SessionLocal() as db:
        handle_update(db, update)


_offset = 0


def poll_updates() -> None:
    """Long-polling for local development, where Telegram can't reach a webhook."""
    global _offset
    updates = telegram.call("getUpdates", {"offset": _offset, "timeout": 0, "allowed_updates": ["message", "callback_query"]}) or []
    with SessionLocal() as db:
        for u in updates:
            _offset = max(_offset, u["update_id"] + 1)
            try:
                handle_update(db, u)
            except Exception:
                db.rollback()
                log.exception("Telegram update failed")


def handle_update(db: Session, update: dict) -> None:
    if "callback_query" in update:
        return _callback(db, update["callback_query"])
    msg = update.get("message") or {}
    chat_id, text = str(msg.get("chat", {}).get("id", "")), (msg.get("text") or "").strip()
    if not chat_id:
        return
    code = text.removeprefix("/start").strip()
    if code.isdigit() and len(code) == 6:
        link = db.get(TelegramLink, code)
        if link and link.expires_at > utcnow():
            user = db.get(User, link.user_id)
            user.telegram_chat_id = chat_id
            user.notif_channels = {**(user.notif_channels or {}), "telegram": True}
            db.delete(link)
            db.commit()
            telegram.send(chat_id, f"You're linked, {user.name.split()[0]}. Event alerts will arrive here. Change this anytime in ShowUp settings.")
            return
        telegram.send(chat_id, "That code has expired. Get a new one in ShowUp settings.")
        return
    if msg.get("photo") or msg.get("document"):
        telegram.send(chat_id, "Poster upload by Telegram is coming soon. For now, use New event in ShowUp.")
        return
    telegram.send(chat_id, "Hi! To link your account, open ShowUp settings and tap Link Telegram.")


def _callback(db: Session, cq: dict) -> None:
    chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    action, _, ref = (cq.get("data") or "").partition(":")
    user = db.scalar(select(User).where(User.telegram_chat_id == chat_id)) if chat_id else None
    if user is None:
        return telegram.answer_callback(cq["id"], "Link your account in ShowUp settings first.")
    try:
        if action == "reg":
            reg = registration.register(db, user, db.get(Event, ref))
            reply = f"You're on the waitlist, #{reg.waitlist_position}." if reg.status == "waitlisted" else "You're in!"
        elif action == "nfm":
            db.add(Feedback(user_id=user.id, event_id=ref, kind="not_for_me"))
            db.commit()
            feedcache.invalidate(user.id)
            reply = "Got it. We'll show fewer like this."
        else:
            reg = db.get(Registration, ref)
            if reg is None or reg.user_id != user.id:
                return telegram.answer_callback(cq["id"], "That registration doesn't exist.")
            if action == "confirm":
                registration.confirm_seat(db, reg)
                reply = "Seat confirmed. See you there!"
            elif action == "yes":
                reg.reminder_confirmed = True
                db.commit()
                reply = "Great, see you there!"
            elif action == "cancel":
                promoted = registration.cancel(db, reg)
                if promoted:
                    jobs.offer_seats(db, promoted)
                reply = "Seat released. Thanks for letting us know."
            else:
                reply = "Sorry, that button has expired."
    except HTTPException as e:
        reply = str(e.detail)
    telegram.answer_callback(cq["id"], reply)
