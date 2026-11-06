"""Best time to schedule: suggests start times that reach more students who fit and are free. Counts only."""

from datetime import datetime, timedelta

from app.timeutil import ist_today, to_ist

from .conftest import login


def _next_weekday(wd: int):
    d = ist_today() + timedelta(days=3)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d


FORM = {"title": "Build an AI chatbot in Python", "description": "Hands-on: build a small chatbot with Python and an LLM API.",
        "category_slug": "ai-ml", "event_type": "workshop", "tags": ["ai", "python"], "mode": "online", "fee_inr": 0,
        "start_time": "11:00", "end_time": "12:30"}


def test_suggests_better_times_when_students_are_busy(client):
    login(client, "organizer")
    r = client.post("/api/organizer/events/best-times", json={**FORM, "date": _next_weekday(1).isoformat()}).json()  # Tuesday 11 AM
    assert r["ready"] and r["pool"] > 0 and r["options"]
    best = r["options"][0]
    assert best["count"] >= r["current"] + 3 and best["count"] >= r["current"] * 1.2
    days = {to_ist(datetime.fromisoformat(o["start_at"].removesuffix("Z"))).date() for o in r["options"]}
    assert len(days) == len(r["options"])  # one option per day, so they're real alternatives
    for o in r["options"]:
        start, end = (datetime.fromisoformat(o[k].removesuffix("Z")) for k in ("start_at", "end_at"))
        assert end - start == timedelta(minutes=90)  # same length as the draft
    assert "@" not in str(r) and "asha" not in str(r).lower()


def test_no_date_no_suggestions_and_not_for_internships(client):
    login(client, "organizer")
    assert client.post("/api/organizer/events/best-times", json=FORM).json()["ready"] is False
    r = client.post("/api/organizer/events/best-times", json={**FORM, "event_type": "internship", "date": _next_weekday(1).isoformat()}).json()
    assert r["ready"] is False


def test_organizers_only(client):
    assert client.post("/api/organizer/events/best-times", json=FORM).status_code == 401
    login(client, "student")
    assert client.post("/api/organizer/events/best-times", json=FORM).status_code == 403
