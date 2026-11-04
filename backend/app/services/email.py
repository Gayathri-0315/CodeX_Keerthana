"""Email over HTTPS through a provider API (Resend or Brevo).

Configured by EMAIL_PROVIDER, EMAIL_API_KEY and EMAIL_FROM. Without a key nothing is sent: the
message is written to the server log with a clear "email skipped" line, so local dev still works.
Every email is one short line plus one primary button (SPEC 8.9).
"""

import html
import logging
import re

import httpx

from ..config import settings

log = logging.getLogger("showup.email")
TIMEOUT = 10.0


def _page(subject: str, body: str, button_label: str | None, button_url: str | None, footer: str) -> str:
    button = (
        f'<p style="margin:28px 0"><a href="{html.escape(button_url)}" style="display:inline-block;background:#0071e3;color:#fff;'
        f'padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:600">{html.escape(button_label or "Open ShowUp")}</a></p>'
        if button_url else ""
    )
    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;max-width:480px;margin:auto;padding:24px;color:#1d1d1f">'
        f'<h2 style="font-weight:600;font-size:22px;margin:0 0 12px">{html.escape(subject)}</h2>'
        f'<p style="font-size:16px;line-height:1.5;margin:0">{html.escape(body)}</p>{button}'
        f'<p style="color:#6e6e73;font-size:13px;line-height:1.4">{html.escape(footer)}</p></div>'
    )


def _sender() -> tuple[str, str]:
    """EMAIL_FROM may be `ShowUp <hello@example.org>` or a bare address."""
    m = re.match(r"^\s*(.*?)\s*<([^>]+)>\s*$", settings.email_from)
    return (m.group(1) or "ShowUp", m.group(2)) if m else ("ShowUp", settings.email_from.strip())


def send_email(to: str, subject: str, body: str, button_label: str | None = None, button_url: str | None = None,
               transactional: bool = False) -> bool:
    """Send one email. Returns True if the provider accepted it (or it was logged because no key is set)."""
    footer = ("You get this because someone used this address on ShowUp. If it wasn't you, ignore this email."
              if transactional else "You get this because email alerts are on in your ShowUp settings.")
    text = body + (f"\n\n{button_label or 'Open'}: {button_url}" if button_url else "") + f"\n\n{footer}"
    if not settings.email_api_key or not settings.email_provider or not settings.email_from:
        log.warning("email skipped (no EMAIL_PROVIDER/EMAIL_API_KEY/EMAIL_FROM) to=%s subject=%r body=%r", to, subject, text)
        return True
    page = _page(subject, body, button_label, button_url, footer)
    name, address = _sender()
    try:
        if settings.email_provider == "resend":
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.email_api_key}"},
                json={"from": f"{name} <{address}>", "to": [to], "subject": subject, "html": page, "text": text},
                timeout=TIMEOUT,
            )
        else:  # brevo
            r = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.email_api_key, "accept": "application/json"},
                json={"sender": {"name": name, "email": address}, "to": [{"email": to}], "subject": subject,
                      "htmlContent": page, "textContent": text},
                timeout=TIMEOUT,
            )
        if r.status_code >= 300:
            log.warning("email to %s failed: %s %s", to, r.status_code, r.text[:200])
            return False
        return True
    except httpx.HTTPError as e:
        log.warning("email to %s failed: %s", to, e)
        return False
