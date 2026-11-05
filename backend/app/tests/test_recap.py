"""Semester recap (feature 4): numbers match the Record, style rules, short version, privacy."""

from collections import Counter
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Organizer, Registration, User
from app.services import feedcache
from app.services.recap import parse_period, style_for
from app.services.record import Attended
from app.timeutil import ist_to_utc

from .conftest import login


def at(d: date, hour: int, slug: str = "ai-ml") -> Attended:
    return Attended(SimpleNamespace(start_at=ist_to_utc(d, hour * 60), end_at=ist_to_utc(d, hour * 60 + 90), event_type="workshop",
                                    category_slug=slug), None)


SAT, MON = date(2026, 10, 3), date(2026, 10, 5)


def label(items):
    return style_for(items, Counter(a.event.category_slug for a in items))["label"]


def test_style_thresholds_are_inclusive_at_60_percent():
    three_weekend = [at(SAT, 12), at(SAT + timedelta(1), 12), at(SAT + timedelta(7), 12)]
    assert label(three_weekend + [at(MON, 12), at(MON + timedelta(1), 12)]) == "Weekend Explorer"  # 3 of 5 = 60%
    assert label(three_weekend[:2] + [at(MON, 12), at(MON + timedelta(1), 12)]) != "Weekend Explorer"  # 2 of 4 = 50%


def test_style_order_breaks_ties():
    # Weekend AND evening: Weekend Explorer is checked first.
    both = [at(SAT, 19), at(SAT + timedelta(1), 19), at(SAT + timedelta(7), 19)]
    assert label(both) == "Weekend Explorer"
    assert label([at(MON, 19), at(MON + timedelta(1), 20), at(MON + timedelta(2), 12)]) == "Night Owl"
    assert label([at(MON, 8), at(MON + timedelta(1), 9), at(MON + timedelta(2), 12)]) == "Early Bird"


def test_deep_diver_curious_mind_rising_regular():
    weekday_noon = [MON + timedelta(k) for k in range(5)]
    assert label([at(d, 12, "design") for d in weekday_noon]) == "Deep Diver"
    slugs = ["ai-ml", "design", "data", "cloud"]
    assert label([at(d, 12, s) for d, s in zip(weekday_noon, slugs)]) == "Curious Mind"
    assert label([at(d, 12, s) for d, s in zip(weekday_noon[:3], ["ai-ml", "design", "data"])]) == "Rising Regular"


def test_reason_uses_real_numbers():
    items = [at(SAT, 12), at(SAT + timedelta(1), 12), at(SAT + timedelta(7), 12), at(MON, 12)]
    assert style_for(items, Counter())["reason"] == "3 of your 4 events were on weekends."


def test_period_parsing():
    assert parse_period("2026-H1")[:2] == (date(2026, 1, 1), date(2026, 6, 30))
    assert parse_period("2026-H2")[2] == "Jul to Dec 2026"
    with pytest.raises(ValueError):
        parse_period("2026-Q3")


def _attend_n(n: int, email="asha@example.com") -> None:
    """Organizer-confirmed check-ins for n past events this half year."""
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
        for k in range(n):
            d = date(2026, 10, 3) + timedelta(weeks=k)
            e = Event(organizer_id=org.id, title=f"Past session {k}", category_slug=["ai-ml", "design", "data"][k % 3],
                      event_type="workshop", mode="in_person", venue_name="Hall", start_at=ist_to_utc(d, 15 * 60),
                      end_at=ist_to_utc(d, 17 * 60), status="published", verification_label="organizer_verified")
            db.add(e)
            db.flush()
            db.add(Registration(user_id=u.id, event_id=e.id, status="attended", checked_in_at=e.start_at))
        db.commit()
    feedcache.invalidate_all()


def test_recap_matches_the_record(client):
    _attend_n(4)
    login(client, "student")
    record = client.get("/api/me/record").json()
    recap = client.get("/api/me/recap?period=2026-H2").json()
    assert recap["events_attended"] == record["events_attended"] == 4
    assert recap["hours"] == record["hours"] == 8.0
    assert recap["longest_streak_weeks"] == record["longest_streak_weeks"] == 4
    assert recap["topics"] == 3 and sum(c["count"] for c in recap["categories"]) == 4
    assert recap["busiest_month"]["month"] == "October" and recap["short"] is False


def test_short_version_and_empty(client):
    login(client, "student")
    assert client.get("/api/me/recap?period=2026-H2").json()["events_attended"] == 0  # the card stays hidden
    _attend_n(2)
    assert client.get("/api/me/recap?period=2026-H2").json()["short"] is True


def test_first_name_only_never_email(client):
    _attend_n(1)
    login(client, "student")
    r = client.get("/api/me/recap?period=2026-H2").json()
    assert r["first_name"] == "Asha" and "@" not in str(r) and "email" not in r


def test_bad_period_and_privacy(client):
    login(client, "student")
    assert client.get("/api/me/recap?period=nope").status_code == 422
    login(client, "organizer")
    assert client.get("/api/me/recap").status_code == 403
