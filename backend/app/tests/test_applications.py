"""Internships without an outside link take applications on ShowUp."""

from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer
from app.timeutil import utcnow

from .conftest import login

NOTE = "I run usability tests for our department app and would love to learn more."


def _internship(link=None, days=5) -> str:
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == "psg-design-society"))
        org.notif_prefs = {}
        org.daily_digest = False
        deadline = utcnow() + timedelta(days=days)
        e = Event(organizer_id=org.id, title="Design Internship", category_slug="design", event_type="internship", mode="online",
                  start_at=deadline, end_at=deadline, fee_inr=0, status="published", verification_label="organizer_verified",
                  risk_score=0, published_at=utcnow(), registration_url=link)
        db.add(e)
        db.commit()
        return e.id


def test_student_applies_once_and_organizer_sees_it(client):
    eid = _internship()
    login(client, "student")
    assert client.get(f"/api/events/{eid}").json()["application"] is None
    r = client.post(f"/api/events/{eid}/apply", json={"note": NOTE, "link": "https://asha.example.org/portfolio"})
    assert r.status_code == 201 and r.json()["status"] == "submitted"
    assert client.get(f"/api/events/{eid}").json()["application"]["status"] == "submitted"
    assert client.post(f"/api/events/{eid}/apply", json={"note": NOTE}).status_code == 409
    login(client, "design@example.com")
    items = client.get(f"/api/organizer/events/{eid}/applications").json()["items"]
    assert items[0]["email"] == "asha@example.com" and items[0]["note"] == NOTE and items[0]["link"].endswith("/portfolio")
    with SessionLocal() as db:
        assert db.scalar(select(Notification).where(Notification.event_id == eid, Notification.title == "New application"))
    login(client, "organizer")  # a different club can't see them
    assert client.get(f"/api/organizer/events/{eid}/applications").status_code == 404


def test_withdraw_and_reapply(client):
    eid = _internship()
    login(client, "student")
    client.post(f"/api/events/{eid}/apply", json={"note": NOTE})
    assert client.delete(f"/api/events/{eid}/apply").status_code == 204
    assert client.get(f"/api/events/{eid}").json()["application"] is None
    assert client.post(f"/api/events/{eid}/apply", json={"note": NOTE}).status_code == 201


def test_rules(client):
    linked = _internship(link="https://jobs.example.org/apply")
    closed = _internship(days=-1)
    login(client, "student")
    assert client.post(f"/api/events/{linked}/apply", json={"note": NOTE}).status_code == 409  # apply on their site
    assert client.post(f"/api/events/{closed}/apply", json={"note": NOTE}).status_code == 409
    eid = _internship()
    assert client.post(f"/api/events/{eid}/apply", json={"note": "hi"}).status_code == 422
    assert client.post(f"/api/events/{eid}/apply", json={"note": NOTE, "link": "javascript:alert(1)"}).status_code == 422
    login(client, "organizer")
    assert client.post(f"/api/events/{eid}/apply", json={"note": NOTE}).status_code == 403
