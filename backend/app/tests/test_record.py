"""Participation record (feature 3): only organizer check-ins count, streaks across week boundaries, private."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Registration, User
from app.services.record import Attended, streaks
from app.timeutil import ist_to_utc

from .conftest import login


def at(d: date) -> Attended:
    return Attended(SimpleNamespace(start_at=ist_to_utc(d, 15 * 60), end_at=ist_to_utc(d, 17 * 60), event_type="workshop"), None)


TODAY = date(2026, 11, 5)  # a Thursday


def test_streak_counts_consecutive_weeks():
    weeks = [TODAY - timedelta(weeks=k) for k in (0, 1, 2)]
    assert streaks([at(d) for d in weeks], TODAY) == (3, 3)


def test_current_week_does_not_break_the_streak_until_it_ends():
    last_two = [TODAY - timedelta(weeks=1), TODAY - timedelta(weeks=2)]
    assert streaks([at(d) for d in last_two], TODAY) == (2, 2)


def test_a_missed_week_breaks_it():
    days = [TODAY - timedelta(weeks=2), TODAY - timedelta(weeks=3), TODAY - timedelta(weeks=4)]
    assert streaks([at(d) for d in days], TODAY) == (0, 3)


def test_week_boundary_is_monday():
    sunday, monday = date(2026, 11, 1), date(2026, 11, 2)  # different weeks, back to back
    assert streaks([at(sunday), at(monday)], date(2026, 11, 3)) == (2, 2)
    assert streaks([at(date(2026, 11, 2)), at(date(2026, 11, 8))], date(2026, 11, 9)) == (1, 1)  # Mon and Sun: same week


def test_empty():
    assert streaks([], TODAY) == (0, 0)


def _attend(client, title="Python Meetup Coimbatore") -> str:
    login(client, "student")
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == title))
    reg = client.post(f"/api/events/{eid}/register").json()
    with SessionLocal() as db:
        token = db.get(Registration, reg["id"]).checkin_token
    login(client, "organizer")
    client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token})
    return eid


def test_record_only_counts_organizer_checkins(client):
    login(client, "student")
    assert client.get("/api/me/record").json()["events_attended"] == 0
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "AI Workshop: Hands-on with LLMs"))
    client.post(f"/api/events/{eid}/register")  # registered, not checked in
    assert client.get("/api/me/record").json()["events_attended"] == 0
    meetup = _attend(client)
    login(client, "student")
    r = client.get("/api/me/record").json()
    assert r["events_attended"] == 1 and r["hours"] == 1.0 and [e["event_id"] for e in r["events"]] == [meetup]


def test_record_is_private(client):
    _attend(client)
    login(client, "student1@example.com")
    assert client.get("/api/me/record").json()["events_attended"] == 0  # only your own
    login(client, "organizer")
    assert client.get("/api/me/record").status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/me/record").status_code == 401
