"""'Your week' (feature 1): free windows, going blocks, at most 2 chips a day, hard filters, speed."""

import time
from datetime import date, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Organizer, User
from app.services import feedcache
from app.timeutil import ist_to_utc, ist_today, to_ist, utcnow

from .conftest import login


def week(client, start: date | None = None) -> dict:
    return client.get("/api/me/week" + (f"?start={start.isoformat()}" if start else "")).json()


def day(w: dict, weekday: int) -> dict:
    return w["days"][weekday]


def test_free_windows_and_busy_time(client):
    login(client, "student")  # Asha: free Sat 2 to 6 PM, Sun 9 AM to 1 PM
    w = week(client)
    assert date.fromisoformat(w["start"]).weekday() == 0 and len(w["days"]) == 7 and w["has_free_time"]
    assert day(w, 5)["free"] == [{"start_min": 840, "end_min": 1080}]
    assert day(w, 6)["free"] == [{"start_min": 540, "end_min": 780}]
    assert day(w, 0)["free"] == [] and day(w, 0)["busy"] == [{"start_min": 360, "end_min": 1320}]
    assert day(w, 5)["busy"] == [{"start_min": 360, "end_min": 840}, {"start_min": 1080, "end_min": 1320}]


def _week_of(title: str) -> date:
    with SessionLocal() as db:
        d = to_ist(db.scalar(select(Event.start_at).where(Event.title == title))).date()
    return d - timedelta(days=d.weekday())


def test_going_block_replaces_the_chip(client):
    login(client, "student")
    with SessionLocal() as db:
        meetup = db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))
        mid, d = meetup.id, to_ist(meetup.start_at).date()
    start = _week_of("Python Meetup Coimbatore")
    before = day(week(client, start), d.weekday())
    assert mid in [f["event_id"] for f in before["fits"]]
    client.post(f"/api/events/{mid}/register")
    after = day(week(client, start), d.weekday())
    assert [g["event_id"] for g in after["going"]] == [mid] and after["going"][0]["kind"] == "going"
    assert mid not in [f["event_id"] for f in after["fits"]]


def _add_events(db, d: date, n: int, **kw) -> list[str]:
    org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
    ids = []
    for i in range(n):
        e = Event(organizer_id=org.id, title=f"Saturday session {i}", description="AI hands-on", category="Workshop",
                  category_slug="ai-ml", event_type="workshop", tags=["ai"], mode="in_person", venue_name="Hall",
                  lat=11.0185, lng=76.97, start_at=ist_to_utc(d, 15 * 60), end_at=ist_to_utc(d, 16 * 60), fee_inr=0,
                  status="published", verification_label="organizer_verified", risk_score=0, published_at=utcnow(), **kw)
        db.add(e)
        db.flush()
        ids.append(e.id)
    db.commit()
    feedcache.invalidate_all()
    return ids


def test_at_most_two_chips_a_day_and_the_rest_on_tap(client):
    login(client, "student")
    start = _week_of("Python Meetup Coimbatore")
    sat = start + timedelta(days=5)
    with SessionLocal() as db:
        _add_events(db, sat, 4)
    d = day(week(client, start), 5)
    assert len(d["recommended"]) == 2 and len(d["fits"]) >= 5
    matches = [f["match"] for f in d["fits"]]
    assert matches == sorted(matches, reverse=True) and d["recommended"] == d["fits"][:2]


def test_hard_filters_apply_eligibility_budget_distance(client):
    login(client, "student")  # budget 200, 20 km, tags college_student, it_dept, year_3
    start = _week_of("Python Meetup Coimbatore")
    sat = start + timedelta(days=5)
    with SessionLocal() as db:
        pricey = _add_events(db, sat, 1, capacity=None)[0]
        db.get(Event, pricey).fee_inr = 900
        far = _add_events(db, sat, 1)[0]
        db.get(Event, far).lat, db.get(Event, far).lng = 11.341, 77.717  # Erode, ~85 km
        closed = _add_events(db, sat, 1)[0]
        db.get(Event, closed).eligibility = {"required_tags": ["mech_dept"], "text": "Mech only"}
        db.commit()
        feedcache.invalidate_all()
    ids = [f["event_id"] for f in day(week(client, start), 5)["fits"]]
    assert pricey not in ids and far not in ids and closed not in ids


def test_empty_state_when_no_free_time(client):
    login(client, "student")
    client.put("/api/availability", json={"slots": []})
    w = week(client)
    assert w["has_free_time"] is False and w["fits_total"] == 0


def test_organizers_have_no_week(client):
    login(client, "organizer")
    assert client.get("/api/me/week").status_code == 403


def test_fast_with_500_events(client):
    login(client, "student")
    start = _week_of("Python Meetup Coimbatore")
    with SessionLocal() as db:
        for k in range(7):
            _add_events(db, start + timedelta(days=k), 70)  # ~500 events on top of the samples
    feedcache.invalidate_all()
    t0 = time.perf_counter()
    cold = client.get(f"/api/me/week?start={start.isoformat()}")
    cold_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    client.get(f"/api/me/week?start={start.isoformat()}")
    warm_ms = (time.perf_counter() - t0) * 1000
    print(f"week endpoint with {cold.json()['fits_total']} fitting of ~515 events: cold {cold_ms:.0f} ms, cached {warm_ms:.0f} ms")
    assert cold.status_code == 200 and warm_ms < 100
