"""Email delivery: SMTP when configured, otherwise printed to the console (dev and demo)."""

import html
import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

log = logging.getLogger("showup.email")


def send_email(to: str, subject: str, body: str, button_label: str | None = None, button_url: str | None = None) -> bool:
    text = body + (f"\n\n{button_label}: {button_url}" if button_url else "")
    button = (
        f'<p><a href="{html.escape(button_url)}" style="display:inline-block;background:#0071e3;color:#fff;'
        f'padding:12px 20px;border-radius:12px;text-decoration:none;font-weight:600">{html.escape(button_label or "Open")}</a></p>'
        if button_url else ""
    )
    page = (
        '<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:480px;margin:auto;color:#1d1d1f">'
        f'<h2 style="font-weight:600">{html.escape(subject)}</h2><p style="font-size:16px">{html.escape(body)}</p>{button}'
        '<p style="color:#6e6e73;font-size:13px">You get this because email alerts are on in ShowUp settings.</p></div>'
    )
    if not settings.smtp_host:
        log.info("EMAIL (console) to=%s subject=%r body=%r", to, subject, text)
        return True
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, settings.smtp_from or settings.smtp_user, to
    msg.set_content(text)
    msg.add_alternative(page, subtype="html")
    try:
        host, _, port = settings.smtp_host.partition(":")
        with smtplib.SMTP(host, int(port or 587), timeout=10) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
        return True
    except Exception as e:
        log.warning("Email to %s failed: %s", to, e)
        return False
