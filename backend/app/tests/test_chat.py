"""Event group chat: only the host and confirmed attendees, simple safety rules, host controls."""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ChatReport, Event, Notification, Organizer, Registration, User
from app.services import chat
from app.timeutil import utcnow

from .conftest import login

SLUG = "coimbatore-ai-club"
ASHA = "asha@example.com"
S1, S2, S3 = "student1@example.com", "student2@example.com", "student3@example.com"


def _setup(status_by_email: dict[str, str]) -> str:
    chat._hits.clear()
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == SLUG))
        start = utcnow() + timedelta(days=5)
        e = Event(organizer_id=org.id, title="Chat Test Meetup", category_slug="ai-ml", event_type="workshop", mode="online",
                  start_at=start, end_at=start + timedelta(hours=2), fee_inr=0, status="published",
                  verification_label="organizer_verified", risk_score=0, published_at=utcnow())
        db.add(e)
        db.flush()
        for email, status in status_by_email.items():
            u = db.scalar(select(User).where(User.email == email))
            u.created_at = utcnow() - timedelta(days=60)
            db.add(Registration(user_id=u.id, event_id=e.id, status=status))
        db.commit()
        return e.id


def _uid(email: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.email == email))


def test_only_host_and_confirmed_attendees_get_in(client):
    eid = _setup({ASHA: "registered", S1: "waitlisted", S2: "cancelled"})
    login(client, "student")
    r = client.get(f"/api/events/{eid}/chat")
    assert r.status_code == 200 and r.json()["role"] == "member" and r.json()["members"] == 2
    for who in (S1, S2, S3, "design@example.com"):
        login(client, who)
        assert client.get(f"/api/events/{eid}/chat").status_code == 404, who
        assert client.post(f"/api/events/{eid}/chat", json={"body": "hi"}).status_code == 404
    login(client, "organizer")
    assert client.get(f"/api/events/{eid}/chat").json()["role"] == "host"
    assert client.get("/api/events/nope/chat").status_code == 404


def test_messages_show_first_names_and_no_emails(client):
    eid = _setup({ASHA: "registered", S1: "attended"})
    login(client, "student")
    assert client.post(f"/api/events/{eid}/chat", json={"body": "Anyone coming from Gandhipuram?"}).status_code == 201
    login(client, "organizer")
    client.post(f"/api/events/{eid}/chat", json={"body": "Welcome all!"})
    login(client, S1)
    r = client.get(f"/api/events/{eid}/chat").json()
    assert [m["sender"]["name"] for m in r["messages"]] == ["Asha", "Coimbatore AI Club"]
    assert r["messages"][1]["sender"]["is_host"] is True
    assert "@example.com" not in str(r)


def test_unread_counts_and_read_marking(client):
    eid = _setup({ASHA: "registered"})
    login(client, "organizer")
    client.post(f"/api/events/{eid}/chat", json={"body": "Doors open at 5"})
    login(client, "student")
    unread = lambda: next(i for i in client.get("/api/me/chats").json()["items"] if i["event_id"] == eid)["unread"]  # noqa: E731
    assert unread() == 1
    client.get(f"/api/events/{eid}/chat")
    assert unread() == 0


def test_safety_rules_block_payments_phones_and_short_links(client):
    eid = _setup({ASHA: "registered"})
    login(client, "student")
    for text in ("pay 200 to asha@okicici for the pass", "call me 9876543210", "see bit.ly/abc"):
        assert client.post(f"/api/events/{eid}/chat", json={"body": text}).status_code == 422, text
    assert client.post(f"/api/events/{eid}/chat", json={"body": "  "}).status_code == 422
    assert client.post(f"/api/events/{eid}/chat", json={"body": "x" * 1001}).status_code == 422


def test_new_accounts_cannot_share_links(client):
    eid = _setup({ASHA: "registered"})
    with SessionLocal() as db:
        db.get(User, _uid(ASHA)).created_at = utcnow()
        db.commit()
    login(client, "student")
    assert client.post(f"/api/events/{eid}/chat", json={"body": "slides at https://example.org/x"}).status_code == 422


def test_ai_check_can_block_and_failure_allows(client):
    eid = _setup({ASHA: "registered"})
    login(client, "student")
    with patch("app.services.llm.classify_message", return_value={"block": True, "reason": "Be kind to others."}):
        r = client.post(f"/api/events/{eid}/chat", json={"body": "you are all idiots"})
        assert r.status_code == 422 and r.json()["error"]["message"] == "Be kind to others."
    with patch("app.services.llm.classify_message", return_value=None):
        assert client.post(f"/api/events/{eid}/chat", json={"body": "See you there"}).status_code == 201


def test_rate_limit(client):
    eid = _setup({ASHA: "registered"})
    login(client, "student")
    codes = [client.post(f"/api/events/{eid}/chat", json={"body": f"msg {i}"}).status_code for i in range(9)]
    assert codes[:8] == [201] * 8 and codes[8] == 429
    chat._hits.clear()


def test_lock_and_announcements_are_host_only(client):
    eid = _setup({ASHA: "registered"})
    with SessionLocal() as db:
        u = db.get(User, _uid(ASHA))
        u.quiet_hours_start = u.quiet_hours_end = "00:00"
        db.commit()
    login(client, "student")
    assert client.post(f"/api/events/{eid}/chat/lock", json={"locked": True}).status_code == 403
    assert client.post(f"/api/events/{eid}/chat", json={"body": "hey", "announcement": True}).status_code == 403
    login(client, "organizer")
    assert client.post(f"/api/events/{eid}/chat/lock", json={"locked": True}).json() == {"locked": True}
    assert client.post(f"/api/events/{eid}/chat", json={"body": "Venue moved to Hall B", "announcement": True}).status_code == 201
    login(client, "student")
    r = client.get(f"/api/events/{eid}/chat").json()
    assert r["locked"] and r["can_post"] is False
    assert client.post(f"/api/events/{eid}/chat", json={"body": "ok"}).status_code == 403
    with SessionLocal() as db:
        n = db.scalar(select(Notification).where(Notification.type == "chat_announcement", Notification.event_id == eid))
        assert n is not None and n.user_id == _uid(ASHA)


def test_chat_turns_read_only_after_the_event(client):
    eid = _setup({ASHA: "attended"})
    with SessionLocal() as db:
        e = db.get(Event, eid)
        e.start_at, e.end_at = utcnow() - timedelta(days=5), utcnow() - timedelta(days=4)
        db.commit()
    login(client, "student")
    r = client.get(f"/api/events/{eid}/chat").json()
    assert r["read_only"] and not r["can_post"]
    assert client.post(f"/api/events/{eid}/chat", json={"body": "thanks!"}).status_code == 409


def test_host_pins_deletes_and_removes(client):
    eid = _setup({ASHA: "registered", S1: "registered"})
    s1 = _uid(S1)
    login(client, "student")
    mid = client.post(f"/api/events/{eid}/chat", json={"body": "hello"}).json()["id"]
    assert client.post(f"/api/chat/messages/{mid}/pin").status_code == 403
    login(client, S1)
    assert client.delete(f"/api/chat/messages/{mid}").status_code == 403
    login(client, "organizer")
    assert client.post(f"/api/chat/messages/{mid}/pin").json() == {"pinned": True}
    assert client.get(f"/api/events/{eid}/chat").json()["pinned"]["id"] == mid
    names = [m["name"] for m in client.get(f"/api/events/{eid}/chat/members").json()["items"]]
    assert "Asha" in names and all("@" not in n for n in names)
    assert client.delete(f"/api/chat/messages/{mid}").status_code == 204
    r = client.get(f"/api/events/{eid}/chat").json()
    assert r["pinned"] is None and r["messages"][0]["hidden"] and r["messages"][0]["body"] is None
    assert client.post(f"/api/events/{eid}/chat/remove/{s1}").status_code == 204
    login(client, S1)
    assert client.get(f"/api/events/{eid}/chat").status_code == 404
    login(client, "student")
    assert client.get(f"/api/events/{eid}/chat/members").status_code == 403


def test_reports_reach_admin_who_can_hide(client):
    eid = _setup({ASHA: "registered", S1: "registered"})
    login(client, S1)
    mid = client.post(f"/api/events/{eid}/chat", json={"body": "buy my notes"}).json()["id"]
    assert client.post(f"/api/chat/messages/{mid}/report", json={"reason": "selling"}).status_code == 409
    login(client, "student")
    assert client.post(f"/api/chat/messages/{mid}/report", json={"reason": "Spam, selling"}).status_code == 204
    assert client.post(f"/api/chat/messages/{mid}/report", json={"reason": "Spam again"}).status_code == 204
    with SessionLocal() as db:
        assert len(db.scalars(select(ChatReport).where(ChatReport.message_id == mid)).all()) == 1
    assert client.get("/api/admin/chat-reports").status_code == 403
    login(client, "admin")
    items = client.get("/api/admin/chat-reports").json()["items"]
    assert items[0]["message"] == "buy my notes"
    assert client.post(f"/api/admin/chat-reports/{items[0]['id']}/hide").json() == {"status": "hidden"}
    assert client.get("/api/admin/chat-reports").json()["items"] == []
    login(client, "student")
    assert client.get(f"/api/events/{eid}/chat").json()["messages"][0]["hidden"]
