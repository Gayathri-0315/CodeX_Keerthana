"""Email over HTTPS (prompt v2, item 6): provider payloads, which alerts email, pause and quiet hours."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Event, Notification, User
from app.services import email as email_service
from app.services import notify
from app.timeutil import utcnow

from .conftest import login


class FakeResponse:
    def __init__(self, status=200):
        self.status_code, self.text = status, "ok"


@pytest.fixture()
def outbox(monkeypatch):
    """Capture provider calls instead of sending."""
    sent = []

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "email_api_key", "re_test_key")
    monkeypatch.setattr(settings, "email_from", "ShowUp <hello@example.org>")
    return sent


def test_resend_payload_is_one_line_and_one_button(outbox):
    assert email_service.send_email("a@example.org", "You're in", "See you Saturday.", "View my pass", "https://x.test/my")
    call = outbox[0]
    assert call["url"] == "https://api.resend.com/emails" and call["headers"]["Authorization"] == "Bearer re_test_key"
    body = call["json"]
    assert body["subject"] == "You're in" and body["to"] == ["a@example.org"] and body["from"] == "ShowUp <hello@example.org>"
    assert body["html"].count("<a ") == 1 and "View my pass" in body["html"] and "See you Saturday." in body["text"]


def test_brevo_payload(outbox, monkeypatch):
    monkeypatch.setattr(settings, "email_provider", "brevo")
    email_service.send_email("a@example.org", "Subject", "Body.", "Open", "https://x.test")
    call = outbox[0]
    assert call["url"] == "https://api.brevo.com/v3/smtp/email" and call["headers"]["api-key"] == "re_test_key"
    assert call["json"]["sender"] == {"name": "ShowUp", "email": "hello@example.org"} and call["json"]["to"] == [{"email": "a@example.org"}]


def test_provider_error_returns_false(outbox, monkeypatch):
    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: FakeResponse(422))
    assert email_service.send_email("a@example.org", "S", "B") is False


def test_no_key_logs_email_skipped(caplog):
    assert email_service.send_email("a@example.org", "Subject", "Body") is True
    assert "email skipped" in caplog.text


def _asha(db, email_on=True) -> User:
    u = db.scalar(select(User).where(User.email == "asha@example.com"))
    u.notif_channels = {"in_app": True, "email": email_on}
    u.quiet_hours_start = u.quiet_hours_end = "00:00"  # no quiet hours unless a test sets them
    db.commit()
    return u


def _event(db) -> Event:
    return db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))


def test_registration_emails_when_email_is_on(client, outbox):
    with SessionLocal() as db:
        _asha(db)
        eid = _event(db).id
    login(client, "student")
    client.post(f"/api/events/{eid}/register")
    subjects = [c["json"]["subject"] for c in outbox]
    assert subjects == ["You're in"]
    assert "/my" in outbox[0]["json"]["html"]  # button goes to the pass


def test_email_respects_the_channel_setting(client, outbox):
    with SessionLocal() as db:
        _asha(db, email_on=False)
        eid = _event(db).id
    login(client, "student")
    client.post(f"/api/events/{eid}/register")
    assert outbox == []


def test_pause_stops_alert_emails_but_not_seat_offers(client, outbox):
    with SessionLocal() as db:
        u = _asha(db)
        u.notif_paused_until = utcnow() + timedelta(days=1)
        db.commit()
        e = _event(db)
        notify.create(db, u, "reminder_24h", e, "Tomorrow, 5 PM", "Python Meetup at the hall. Still going?")
        notify.create(db, u, "seat_opened", e, "A seat just opened up", "Python Meetup is yours for 15 min.")
    assert [c["json"]["subject"] for c in outbox] == ["A seat just opened up"]


def test_quiet_hours_hold_emails_until_they_end(client, outbox):
    with SessionLocal() as db:
        u = _asha(db)
        u.quiet_hours_start, u.quiet_hours_end = "00:00", "23:59"
        db.commit()
        e = _event(db)
        n = notify.create(db, u, "cancelled_event", e, "Event cancelled", "Python Meetup was cancelled by the organizer.")
        assert outbox == [] and not db.get(Notification, n.id).channel_sent
        u.quiet_hours_start = u.quiet_hours_end = "00:00"
        db.commit()
        assert notify.flush_pending(db) >= 1
    assert [c["json"]["subject"] for c in outbox] == ["Event cancelled"]


def test_two_hour_reminder_is_in_app_only(client, outbox):
    with SessionLocal() as db:
        u = _asha(db)
        notify.create(db, u, "reminder_2h", _event(db), "In 2 hours", "Python Meetup starts at 5 PM.")
    assert outbox == []


def test_every_listed_type_has_a_button():
    for kind in ["match", "similar", "deadline", "registered", "waitlisted", "seat_opened", "reminder_24h",
                 "reminder_leave_by", "cancelled_event", "message", "new_message"]:
        label, url = notify.email_button(Notification(type=kind, event_id="e1", payload={}))
        assert label and url.startswith("http")


def test_admin_test_email_is_admin_only(client, outbox):
    login(client, "student")
    assert client.post("/api/admin/test-email").status_code == 403
    login(client, "admin")
    r = client.post("/api/admin/test-email").json()
    assert r["status"] == "sent" and outbox[-1]["json"]["to"] == ["admin@example.com"]


def test_admin_test_email_without_provider_says_skipped(client):
    login(client, "admin")
    assert client.post("/api/admin/test-email").json()["status"] == "skipped"
