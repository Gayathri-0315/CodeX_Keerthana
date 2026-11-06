"""Learned show-up prediction: only used with enough data and when it beats the rules; private nudges; organizer advice."""

import random
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer, Registration, User
from app.routers.organizer import turnout_advice
from app.services import jobs, showup_model
from app.services.showup_model import Features
from app.timeutil import utcnow

from .conftest import login


def _rows(n=600, seed=1):
    """Synthetic history: people who live far away and haven't confirmed mostly don't come."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        d = rng.uniform(0, 30)
        confirmed = rng.random() < 0.5
        p = 0.92 - 0.025 * d + (0.15 if confirmed else -0.1)
        f = Features(with_friend=False, interest=70, distance_km=d, days_before=rng.uniform(0, 20), confirmed=confirmed,
                     past_rate=None, slack_min=None, start=datetime(2026, 10, 3, 10), fee_inr=0)
        rows.append((f, int(rng.random() < max(0.02, min(0.98, p))), f"e{i % 40}"))
    return rows


def test_not_used_without_enough_history(client):
    showup_model.reset_cache()
    with SessionLocal() as db:
        report = showup_model.train(db, _rows(50))
        assert report["used"] is False and "Not enough" in report["reason"]
        assert showup_model.current(db) is None


def test_learns_the_pattern_and_beats_the_rules(client):
    showup_model.reset_cache()
    with SessionLocal() as db:
        report = showup_model.train(db, _rows())
        assert report["used"] is True and report["log_loss_learned"] < report["log_loss_rules"]
        model = showup_model.current(db)
    base = dict(with_friend=False, interest=70, days_before=3, past_rate=None, slack_min=None, start=datetime(2026, 10, 3, 10), fee_inr=0)
    near, far = Features(distance_km=1, confirmed=True, **base), Features(distance_km=28, confirmed=False, **base)
    assert showup_model.predict(model, near) > 0.8 > 0.4 > showup_model.predict(model, far)
    assert model["weights_named"]["distance"] < 0 < model["weights_named"]["confirmed"]
    showup_model.reset_cache()
    with SessionLocal() as db:
        showup_model._save(db, None, {"used": False})


def test_advice_is_about_totals_only():
    assert "6 seats will likely go unused" in turnout_advice(40, 34, 40, 10, False)
    assert "let 6 more in" in turnout_advice(40, 34, 40, 10, False)
    assert turnout_advice(40, 34, 40, 10, True) is None  # ended
    assert "Expect about 15 of 20" in turnout_advice(20, 15, None, 0, False)
    assert turnout_advice(20, 19, None, 0, False) is None


def test_private_seat_check_only_for_likely_no_shows_when_others_wait(client):
    from app.services.showup_score import Likelihood

    now = utcnow()
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == "coimbatore-ai-club"))
        start = now + timedelta(hours=5)
        e = Event(organizer_id=org.id, title="Full Workshop", category_slug="ai-ml", event_type="workshop", mode="in_person",
                  venue_name="Hall", start_at=start, end_at=start + timedelta(hours=2), fee_inr=0, capacity=2, status="published",
                  verification_label="organizer_verified", risk_score=0, published_at=now)
        db.add(e)
        db.flush()
        users = db.scalars(select(User).where(User.role == "student").limit(3)).all()
        for u in users:
            u.quiet_hours_start = u.quiet_hours_end = "00:00"
        unsure = Registration(user_id=users[0].id, event_id=e.id, status="registered")
        sure = Registration(user_id=users[1].id, event_id=e.id, status="registered")
        db.add_all([unsure, sure, Registration(user_id=users[2].id, event_id=e.id, status="waitlisted", waitlist_position=1)])
        db.commit()
        fake = lambda _db, user, _e, _r: Likelihood(0.3 if user.id == users[0].id else 0.9)  # noqa: E731
        with patch.object(jobs.registration, "compute_likelihood", side_effect=fake):
            assert jobs.send_seat_checks(db, now) == 1
            assert jobs.send_seat_checks(db, now) == 0  # once
        sent = db.scalars(select(Notification).where(Notification.type == "seat_check", Notification.event_id == e.id)).all()
        assert [n.user_id for n in sent] == [users[0].id]  # only the likely no-show; not the sure one, not the waitlist


def test_organizer_analytics_says_which_estimate(client):
    login(client, "organizer")
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == "coimbatore-ai-club"))
        eid = db.scalar(select(Event.id).where(Event.organizer_id == org.id, Event.status == "published"))
    a = client.get(f"/api/organizer/events/{eid}/analytics").json()
    assert a["estimate"] == "rules" and "advice" in a
    assert "asha" not in str(a).lower()
