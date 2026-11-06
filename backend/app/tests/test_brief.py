"""Daily brief: only important things, the AI can only pick given items, one message a day, no student details."""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer, Report, User
from app.services import brief
from app.services.brief import Item, compose
from app.timeutil import utcnow

from .conftest import login


def test_rules_pick_the_highest_priorities():
    items = [Item(30, "low", "/"), Item(95, "scam", "/"), Item(70, "mid", "/")] + [Item(10, f"noise {i}", "/") for i in range(8)]
    b = compose(items, "admin")
    assert b["source"] == "rules" and [i["text"] for i in b["items"][:3]] == ["scam", "mid", "low"] and len(b["items"]) == 5


def test_model_can_only_choose_given_items():
    items = [Item(90, "A was reported 2 times.", "/a"), Item(60, "B has 3 new applications.", "/b")]
    fake = {"headline": "Two things", "items": [{"n": 1, "text": "A was reported twice; check it."}, {"n": 7, "text": "Invented"},
                                                {"n": "x"}, {"n": 1, "text": "dupe"}]}
    with patch.object(brief.llm, "chat_json", return_value=fake):
        b = compose(items, "organizer")
    assert b["source"] == "ai" and [(i["text"], i["path"]) for i in b["items"]] == [("A was reported twice; check it.", "/a")]


def test_nothing_important_means_no_message(client):
    with SessionLocal() as db:
        now = utcnow().replace(hour=4)  # 9:30 AM IST
        with patch.object(brief, "for_user", return_value={"headline": "x", "items": [{"text": "minor", "path": "/", "priority": 20}]}):
            assert brief.send_daily_briefs(db, now) == 0


def test_one_brief_a_morning_for_organizers_with_something_urgent(client):
    now = utcnow().replace(hour=4, minute=0)  # 9:30 AM IST
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == "coimbatore-ai-club"))
        org.notif_prefs = {}
        e = db.scalar(select(Event).where(Event.organizer_id == org.id, Event.status == "published"))
        student = db.scalar(select(User).where(User.email == "asha@example.com"))
        db.add(Report(event_id=e.id, reporter_id=student.id, reason="Wrong venue", created_at=now - timedelta(hours=2)))
        u = db.get(User, org.user_id)
        u.quiet_hours_start = u.quiet_hours_end = "00:00"
        db.commit()
        assert brief.send_daily_briefs(db, now.replace(hour=1)) == 0  # 6:30 AM IST: too early
        assert brief.send_daily_briefs(db, now) >= 1
        n = db.scalar(select(Notification).where(Notification.user_id == org.user_id, Notification.type == "daily_brief"))
        assert n is not None and "asha" not in (n.title + n.body).lower()
        assert brief.send_daily_briefs(db, now + timedelta(hours=1)) == 0  # once a day


def test_endpoint_for_organizers_and_admins_only(client):
    login(client, "student")
    assert client.get("/api/me/brief").status_code == 403
    login(client, "organizer")
    b = client.get("/api/me/brief").json()
    assert "headline" in b and all({"text", "path"} <= set(i) for i in b["items"])
    assert "@example.com" not in str(b)
    login(client, "admin")
    assert client.get("/api/me/brief").status_code == 200
