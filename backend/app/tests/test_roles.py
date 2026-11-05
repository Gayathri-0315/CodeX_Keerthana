"""Guests can browse; students and organizers can't use each other's screens (prompt v2, items 9 and 10)."""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event

from .conftest import login


def event_id(title="Python Meetup Coimbatore") -> str:
    with SessionLocal() as db:
        return db.scalar(select(Event.id).where(Event.title == title))


def test_guest_can_browse_and_open_events_without_personal_data(client):
    r = client.get("/api/public/events?limit=50").json()
    assert r["items"] and all(i["guest"] and i["fits"] is None and i["reasons"] == [] for i in r["items"])
    with SessionLocal() as db:
        statuses = {db.get(Event, i["id"]).status for i in r["items"]}
    assert statuses == {"published"}
    detail = client.get(f"/api/events/{event_id()}").json()
    assert detail["guest"] and detail["title"] == "Python Meetup Coimbatore" and detail["registration"] is None
    assert client.get("/api/public/categories").json()["categories"]


def test_guest_cannot_see_blocked_events(client):
    with SessionLocal() as db:
        blocked = db.scalar(select(Event.id).where(Event.status == "blocked"))
    assert blocked and client.get(f"/api/events/{blocked}").status_code == 404
    assert blocked not in {i["id"] for i in client.get("/api/public/events?limit=50").json()["items"]}


@pytest.mark.parametrize("method,path", [
    ("post", "/api/events/{id}/register"), ("post", "/api/events/{id}/save"), ("get", "/api/feed"),
    ("get", "/api/registrations/me"), ("get", "/api/alerts"),
])
def test_guest_actions_need_sign_in(client, method, path):
    assert getattr(client, method)(path.format(id=event_id())).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", "/api/feed"), ("get", "/api/feed/explore"), ("get", "/api/feed/count"), ("get", "/api/availability"),
    ("put", "/api/availability"), ("get", "/api/registrations/me"), ("post", "/api/events/{id}/save"),
    ("post", "/api/events/{id}/register"), ("post", "/api/events/{id}/dismiss"), ("get", "/api/alerts"),
])
def test_organizers_cannot_use_student_endpoints(client, method, path):
    login(client, "organizer")
    kwargs = {"json": {"slots": []}} if method == "put" else {}
    assert getattr(client, method)(path.format(id=event_id()), **kwargs).status_code == 403


@pytest.mark.parametrize("method,path", [
    ("get", "/api/organizer/summary"), ("get", "/api/organizer/events"), ("post", "/api/organizer/events"),
    ("get", "/api/admin/review-queue"), ("post", "/api/admin/test-email"),
])
def test_students_cannot_use_organizer_or_admin_endpoints(client, method, path):
    login(client, "student")
    kwargs = {"json": {"title": "x"}} if method == "post" and "organizer" in path else {}
    assert getattr(client, method)(path, **kwargs).status_code == 403


def test_organizer_sees_public_event_detail(client):
    login(client, "organizer")
    detail = client.get(f"/api/events/{event_id()}").json()
    assert detail["guest"] and detail["fits"] is None


def test_public_categories_have_all_thirteen_with_live_counts(client):
    cats = client.get("/api/public/categories").json()["categories"]
    assert len(cats) == 13 and cats[0] == {**cats[0], "slug": "ai-ml", "name": "AI & ML", "emoji": "🤖"}
    total = client.get("/api/public/events?limit=50").json()["total"]
    assert 0 < sum(c["count"] for c in cats) <= total


def test_publishing_needs_a_category(client):
    login(client, "organizer")
    form = {"title": "Robot night", "date": "2030-01-05", "start_time": "18:00", "end_time": "20:00",
            "venue_name": "Hall", "mode": "in_person"}
    saved = client.post("/api/organizer/events", json=form).json()
    r = client.post(f"/api/organizer/events/{saved['id']}/publish")
    assert r.status_code == 422 and "a category" in r.json()["error"]["message"]


def test_category_is_suggested_from_tags():
    from app.services.categories import suggest

    assert suggest(["cybersecurity"]) == "cyber-security"
    assert suggest(["python", "ai"]) == "ai-ml"
    assert suggest([], "Inter-college Football Cup") == "sports"
    assert suggest(["misc"]) is None
