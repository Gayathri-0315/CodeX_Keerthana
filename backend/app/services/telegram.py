"""Telegram Bot API over plain HTTPS (no extra dependency). Everything degrades to a no-op without a token."""

import json
import logging
import urllib.request

from ..config import settings

log = logging.getLogger("showup.telegram")
API = "https://api.telegram.org/bot{token}/{method}"


def enabled() -> bool:
    return bool(settings.telegram_bot_token)


def call(method: str, payload: dict, timeout: float = 10) -> dict | None:
    if not enabled():
        return None
    req = urllib.request.Request(
        API.format(token=settings.telegram_bot_token, method=method),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data.get("result") if data.get("ok") else None
    except Exception as e:
        log.info("Telegram %s failed: %s", method, e)
        return None


def send(chat_id: str, text: str, buttons: list[dict] | None = None) -> bool:
    """`buttons`: [{"text": "View", "url": ...} | {"text": "Register", "callback_data": "reg:<id>"}]."""
    payload: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [buttons[i : i + 2] for i in range(0, len(buttons), 2)]}
    return call("sendMessage", payload) is not None


def answer_callback(callback_id: str, text: str) -> None:
    call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


def bot_link(code: str | None = None) -> str | None:
    if not settings.telegram_bot_username:
        return None
    return f"https://t.me/{settings.telegram_bot_username}" + (f"?start={code}" if code else "")
