"""Admins can verify any organizer from the Organizers list; badges on their events follow."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer

from .conftest import login

NEW = "quickcareers-hub"  # seeded as a "new" organizer


def _org_id():
    with SessionLocal() as db:
        return db.scalar(select(Organizer.id).where(Organizer.slug == NEW))


def test_only_admins(client):
    login(client, "organizer")
    assert client.get("/api/admin/organizers").status_code == 403
    assert client.post(f"/api/admin/organizers/{_org_id()}/trust", json={"level": "verified"}).status_code == 403


def test_list_puts_unverified_first_and_searches(client):
    login(client, "admin")
    items = client.get("/api/admin/organizers").json()["items"]
    assert items[0]["trust_level"] == "new" and {"name", "email", "events", "trust_level"} <= set(items[0])
    found = client.get("/api/admin/organizers", params={"q": "quickcareers"}).json()["items"]
    assert [o["slug"] for o in found] == [NEW]


def test_verify_updates_badges_and_tells_the_organizer(client):
    oid = _org_id()
    with SessionLocal() as db:
        db.scalar(select(Organizer).where(Organizer.id == oid)).notif_prefs = {}
        e = db.scalar(select(Event).where(Event.organizer_id == oid))
        e.verification_label = "details_reviewed"
        db.commit()
        eid = e.id
    login(client, "admin")
    assert client.post(f"/api/admin/organizers/{oid}/trust", json={"level": "verified"}).json()["trust_level"] == "verified"
    with SessionLocal() as db:
        assert db.get(Event, eid).verification_label == "organizer_verified"
        assert db.scalar(select(Notification).where(Notification.type == "org_review", Notification.title == "Your organization is verified"))
    assert client.get(f"/api/public/clubs/{NEW}").json()["trust_label"] == "Verified"
    assert client.post(f"/api/admin/organizers/{oid}/trust", json={"level": "new"}).json()["trust_level"] == "new"
    with SessionLocal() as db:
        assert db.get(Event, eid).verification_label == "details_reviewed"
    assert client.post(f"/api/admin/organizers/{oid}/trust", json={"level": "boss"}).status_code == 422
