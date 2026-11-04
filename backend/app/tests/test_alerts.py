"""Saved alerts: 'Remind me of similar events' (prompt v2, item 2)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer, User
from app.services import alerts, jobs
from app.timeutil import ist_to_utc, to_ist, utcnow

from .conftest import login

HACKATHON = "ML Hackathon: Build for Kovai"  # Sun 9 AM to 5 PM; Asha is free Sun 9 AM to 1 PM, so it's in Almost


def hackathon_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Event.id).where(Event.title == HACKATHON))


def publish(db, title: str, tags: list[str], start_min: int, end_min: int, same_day_as: str = HACKATHON) -> Event:
    """A clean event from the trusted club, on the same date as the hackathon."""
    day = to_ist(db.scalar(select(Event.start_at).where(Event.title == same_day_as))).date()
    org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
    e = Event(organizer_id=org.id, title=title, description="Hands-on session.", category="Workshop", tags=tags,
              mode="in_person", venue_name="Hall", lat=11.0185, lng=76.97, start_at=ist_to_utc(day, start_min),
              end_at=ist_to_utc(day, end_min), registration_deadline=ist_to_utc(day, start_min) - timedelta(hours=2),
              fee_inr=0, status="published", verification_label="organizer_verified", risk_score=0, published_at=utcnow())
    db.add(e)
    db.commit()
    return e


def asha(db) -> User:
    return db.scalar(select(User).where(User.email == "asha@example.com"))


def similar_count(db, user_id: str) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.type == "similar"))


def test_create_list_and_delete_alert(client):
    login(client, "student")
    r = client.post("/api/alerts", json={"event_id": hackathon_id()})
    assert r.status_code == 201
    a = r.json()
    assert a["tags"] == ["hackathons", "ai", "data"] and a["window"] == "Sundays, 9 AM to 5 PM"
    assert client.post("/api/alerts", json={"event_id": hackathon_id()}).json()["id"] == a["id"]  # no duplicates
    assert [x["id"] for x in client.get("/api/alerts").json()["items"]] == [a["id"]]
    assert client.delete(f"/api/alerts/{a['id']}").status_code == 204
    assert client.get("/api/alerts").json()["items"] == []


def test_organizers_cannot_save_alerts(client):
    login(client, "organizer")
    assert client.post("/api/alerts", json={"event_id": hackathon_id()}).status_code == 403


def test_matching_event_that_fits_sends_one_alert(client):
    login(client, "student")
    client.post("/api/alerts", json={"event_id": hackathon_id()})
    with SessionLocal() as db:
        e = publish(db, "Mini Hack Morning", ["hackathons"], 10 * 60, 12 * 60)  # inside her Sun 9 to 1 free time
        assert alerts.suggest_similar(db, e) == 1
        assert alerts.suggest_similar(db, e) == 0  # dedupe
        n = db.scalar(select(Notification).where(Notification.type == "similar", Notification.event_id == e.id))
        assert n.user_id == asha(db).id and n.title == "Something like the one you missed" and len(n.body) <= 90


def test_no_alert_without_shared_tags_or_outside_window(client):
    login(client, "student")
    client.post("/api/alerts", json={"event_id": hackathon_id()})
    with SessionLocal() as db:
        other_topic = publish(db, "Sketching Morning", ["design"], 10 * 60, 12 * 60)
        late = publish(db, "Night Hack", ["hackathons"], 19 * 60, 21 * 60)  # after the saved 9-5 window
        assert alerts.suggest_similar(db, other_topic) == 0
        assert alerts.suggest_similar(db, late) == 0
        assert similar_count(db, asha(db).id) == 0


def test_no_alert_when_it_fails_hard_filters(client):
    login(client, "student")
    client.post("/api/alerts", json={"event_id": hackathon_id()})
    with SessionLocal() as db:
        clash = publish(db, "All-day Hack", ["ai"], 9 * 60, 17 * 60)  # same clash as before: still not free
        pricey = publish(db, "Paid Hack", ["ai"], 10 * 60, 12 * 60)
        pricey.fee_inr = 5000
        db.commit()
        assert alerts.suggest_similar(db, clash) == 0 and alerts.suggest_similar(db, pricey) == 0


def test_alert_respects_pause_and_weekly_cap(client):
    login(client, "student")
    client.post("/api/alerts", json={"event_id": hackathon_id()})
    with SessionLocal() as db:
        u = asha(db)
        u.notif_paused_until = utcnow() + timedelta(days=1)
        db.commit()
        e = publish(db, "Mini Hack Morning", ["hackathons"], 10 * 60, 12 * 60)
        assert alerts.suggest_similar(db, e) == 0
        u.notif_paused_until, u.notif_max_per_week = None, 1
        db.add(Notification(user_id=u.id, type="match", title="t", body="b"))  # cap already used this week
        db.commit()
        assert alerts.suggest_similar(db, e) == 0


def test_publishing_runs_saved_alerts(client):
    login(client, "student")
    client.post("/api/alerts", json={"event_id": hackathon_id()})
    with SessionLocal() as db:
        e = publish(db, "Mini Hack Morning", ["hackathons"], 10 * 60, 12 * 60)
        jobs.suggest_for_event(db, e.id)
        kinds = db.scalars(select(Notification.type).where(Notification.user_id == asha(db).id, Notification.event_id == e.id)).all()
        assert len(kinds) == 1 and kinds[0] in ("match", "similar")  # never both for one event
