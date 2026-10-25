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
from ..services import feedcache, jobs, listing, registration, telegram
from ..services.extraction import extract_poster
from ..services.uploads import public_url, read_upload
from ..timeutil import fmt_range, iso_utc, to_ist, utcnow

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
        return _poster(db, chat_id, msg)
    telegram.send(chat_id, "Hi! To link your account, open ShowUp settings and tap Link Telegram. Organizers can send me an event poster.")


def _poster(db: Session, chat_id: str, msg: dict) -> None:
    """An organizer sends a poster: extract, save a draft, run the trust check, offer to publish."""
    user = db.scalar(select(User).where(User.telegram_chat_id == chat_id))
    if user is None or user.organizer is None:
        telegram.send(chat_id, "Only linked organizer accounts can post events here. Link Telegram from ShowUp settings first.")
        return
    file_id = msg["photo"][-1]["file_id"] if msg.get("photo") else msg["document"]["file_id"]
    name = (msg.get("document") or {}).get("file_name") or "telegram-poster.jpg"
    data = telegram.download(file_id)
    if data is None:
        telegram.send(chat_id, "I couldn't download that file. Send a photo or PDF under 8 MB.")
        return
    telegram.send(chat_id, "Reading your poster...")
    try:
        upload = read_upload(data, name)
    except HTTPException as e:
        telegram.send(chat_id, str(e.detail))
        return
    result = extract_poster(db, upload)
    org = user.organizer
    event = Event(organizer_id=org.id, status="draft")
    listing.apply_form(db, event, listing.form_from_extraction(result["fields"], public_url(upload.stored_name), "telegram"))
    if not event.title:
        event.title = "Untitled event"
    db.add(event)
    db.flush()
    gate = listing.run_gate(db, org, event, event.id)
    event.risk_score, event.risk_reasons, event.duplicate_of = gate.score, gate.reasons, gate.duplicate_of
    db.commit()
    telegram.send(chat_id, poster_summary(event, gate, result), [
        {"text": "Confirm and publish", "callback_data": f"pub:{event.id}"},
        {"text": "Edit on web", "url": f"{settings.public_url}/organizer/event/{event.id}/edit"},
        {"text": "Cancel", "callback_data": f"del:{event.id}"},
    ])


CHECK_LABELS = {"title": "title", "date": "date", "start_time": "start time", "end_time": "end time", "venue_name": "venue",
                "address": "address", "fee_inr": "fee", "registration_deadline": "registration deadline"}


def poster_summary(event: Event, gate, result: dict) -> str:
    lines = ["Here's what I read:", "", event.title]
    if event.start_at and event.end_at:
        s, e = to_ist(event.start_at), to_ist(event.end_at)
        lines.append(f"{s.strftime('%a, %d %b')} · {fmt_range(s, e)}")
    lines += [event.venue_name or ("Online" if event.mode == "online" else "Venue missing"), "Free" if event.fee_inr == 0 else f"₹{event.fee_inr:,}", ""]
    unsure = [CHECK_LABELS[f] for f in result.get("low_confidence", []) if f in CHECK_LABELS]
    if unsure:
        lines.append("Please check: " + ", ".join(unsure) + ".")
    verdict = {"low": "Looks good", "medium": "Would show as unverified", "high": "Can't be published like this"}[gate.level]
    lines.append(f"Trust check: {verdict}.")
    lines += [f"• {r}" for r in gate.reasons if gate.level != "low"]
    if result.get("message"):
        lines.append(result["message"])
    return "\n".join(lines)


def _callback(db: Session, cq: dict) -> None:
    chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    action, _, ref = (cq.get("data") or "").partition(":")
    user = db.scalar(select(User).where(User.telegram_chat_id == chat_id)) if chat_id else None
    if user is None:
        return telegram.answer_callback(cq["id"], "Link your account in ShowUp settings first.")
    try:
        if action in ("pub", "del"):
            event = db.get(Event, ref)
            if event is None or user.organizer is None or event.organizer_id != user.organizer.id:
                return telegram.answer_callback(cq["id"], "That event doesn't exist or isn't yours.")
            if action == "del":
                if event.status != "draft":
                    return telegram.answer_callback(cq["id"], "Only drafts can be cancelled here.")
                db.delete(event)
                db.commit()
                reply = "Draft deleted."
            else:
                status = listing.publish(db, user.organizer, event)
                reply = {"published": "Published! It's live for students.", "pending_review": "Submitted for review.",
                         "blocked": "Blocked by the trust check. Edit it on the web to fix it."}[status]
                telegram.send(chat_id, reply)
        elif action == "reg":
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
