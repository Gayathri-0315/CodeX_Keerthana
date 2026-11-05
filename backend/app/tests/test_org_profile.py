"""Organizer profile settings: profile, trust and verification, notifications, readable data download."""

import io
from datetime import timedelta

from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer, User
from app.services import org_alerts
from app.timeutil import utcnow

from .conftest import login


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (0, 113, 227)).save(buf, "PNG")
    return buf.getvalue()


def test_profile_round_trip_and_validation(client):
    login(client, "organizer")
    p = client.get("/api/organizer/profile").json()
    assert p["org_name"] == "Coimbatore AI Club" and p["trust_label"] == "Trusted" and p["official_email"] == "club@example.com"
    assert p["track_record"]["events_hosted"] >= 9 and p["notif_prefs"]["new_registration"] is True
    r = client.patch("/api/organizer/profile", json={"org_type": "college_club", "city": "Coimbatore", "bio": "We run AI meetups.",
                                                     "website": "https://aiclub.example.org", "show_official_email": True})
    assert r.status_code == 200 and r.json()["org_type"] == "college_club" and r.json()["website"] == "https://aiclub.example.org"
    assert client.patch("/api/organizer/profile", json={"website": "http://not-secure.example.org"}).status_code == 422
    assert client.patch("/api/organizer/profile", json={"notif_prefs": {"bogus": True}}).status_code == 422


def test_students_cannot_open_organizer_profile(client):
    login(client, "student")
    assert client.get("/api/organizer/profile").status_code == 403


def test_public_event_shows_profile_and_email_only_when_allowed(client):
    login(client, "organizer")
    client.patch("/api/organizer/profile", json={"bio": "We run AI meetups.", "show_official_email": False})
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    client.post("/api/auth/logout")
    org = client.get(f"/api/events/{eid}").json()["organizer"]
    assert org["bio"] == "We run AI meetups." and org["contact_email"] is None
    login(client, "organizer")
    client.patch("/api/organizer/profile", json={"show_official_email": True})
    client.post("/api/auth/logout")
    assert client.get(f"/api/events/{eid}").json()["organizer"]["contact_email"] == "club@example.com"


def test_logo_upload(client):
    login(client, "organizer")
    r = client.post("/api/organizer/profile/logo", files={"file": ("logo.png", png(), "image/png")}).json()
    assert r["logo_url"].startswith("/api/files/") and client.get(r["logo_url"]).status_code == 200


def test_verification_request_is_private_and_admin_approves(client):
    login(client, "neworg@example.com")
    r = client.post("/api/organizer/profile/verification", data={"document_type": "college_id", "note": "Club lead ID"},
                    files={"file": ("id.png", png(), "image/png")})
    assert r.status_code == 200 and r.json()["verification"]["status"] == "pending"
    again = client.post("/api/organizer/profile/verification", data={"document_type": "college_id"},
                        files={"file": ("id.png", png(), "image/png")})
    assert again.status_code == 409
    login(client, "admin")
    req = client.get("/api/admin/verification-requests").json()["items"][0]
    doc = client.get(f"/api/admin/verification-requests/{req['id']}/document")
    assert doc.status_code == 200 and doc.headers["cache-control"] == "no-store"
    login(client, "student")
    assert client.get(f"/api/admin/verification-requests/{req['id']}/document").status_code == 403
    login(client, "admin")
    assert client.post(f"/api/admin/verification-requests/{req['id']}/approve").json()["trust_level"] == "verified"
    login(client, "neworg@example.com")
    p = client.get("/api/organizer/profile").json()
    assert p["trust_label"] == "Verified" and p["verification"]["status"] == "approved"
    assert client.get("/api/notifications").json()["items"][0]["title"] == "Your organization is verified"


def _club_user(db):
    org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
    return org, db.get(User, org.user_id)


def test_registration_and_cancellation_alert_the_organizer(client):
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    login(client, "student")
    reg = client.post(f"/api/events/{eid}/register").json()
    client.post(f"/api/registrations/{reg['id']}/cancel")
    with SessionLocal() as db:
        _, owner = _club_user(db)
        kinds = [k for (k,) in db.execute(select(Notification.type).where(Notification.user_id == owner.id, Notification.event_id == eid))]
    assert kinds.count("org_registration") == 1 and kinds.count("org_cancellation") == 1


def test_switched_off_alerts_are_not_sent(client):
    login(client, "organizer")
    client.patch("/api/organizer/profile", json={"notif_prefs": {"new_registration": False}})
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    login(client, "student")
    client.post(f"/api/events/{eid}/register")
    with SessionLocal() as db:
        _, owner = _club_user(db)
        assert db.scalar(select(Notification.id).where(Notification.user_id == owner.id, Notification.type == "org_registration")) is None


def test_daily_digest_collects_alerts_into_one_summary(client):
    login(client, "organizer")
    client.patch("/api/organizer/profile", json={"daily_digest": True})
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    for who in ("student", "student2@example.com"):
        login(client, who)
        client.post(f"/api/events/{eid}/register")
    with SessionLocal() as db:
        _, owner = _club_user(db)
        held = db.scalars(select(Notification).where(Notification.user_id == owner.id, Notification.type == "org_registration")).all()
        assert len(held) == 2 and all(n.channel_sent == {"digest": "pending"} for n in held)
        evening = utcnow().replace(hour=14, minute=30)  # 8 PM IST
        assert org_alerts.send_digests(db, evening) == 1
        assert org_alerts.send_digests(db, evening) == 0  # once a day
        digest = db.scalar(select(Notification).where(Notification.user_id == owner.id, Notification.type == "org_digest"))
        assert digest.body.startswith("2 new registrations across 1 event")


def test_organizer_gets_one_reminder_before_their_event(client):
    with SessionLocal() as db:
        e = db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))
        at = e.start_at - timedelta(hours=20)
        assert org_alerts.send_event_reminders(db, at) >= 1
        assert org_alerts.send_event_reminders(db, at) == 0


def test_download_my_data_is_a_readable_document(client):
    login(client, "organizer")
    r = client.get("/api/organizer/profile/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert 'attachment; filename="showup-coimbatore-ai-club-data.txt"' == r.headers["content-disposition"]
    text = r.text
    assert text.startswith("ShowUp: your organizer data") and "ORGANIZATION" in text and "Python Meetup Coimbatore" in text
    assert "{" not in text and "asha@example.com" not in text  # not JSON, and no student details
