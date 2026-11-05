"""Event Q&A (only from the event's details) and the host's chat summary."""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ChatMessage, Event, Notification, Organizer, Registration, User
from app.services import assist, chat
from app.timeutil import utcnow

from .conftest import login

SLUG = "coimbatore-ai-club"
ASHA, S1 = "asha@example.com", "student1@example.com"


def _event(fee=150, members=(ASHA,)) -> str:
    chat._hits.clear()
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.slug == SLUG))
        start = utcnow() + timedelta(days=4)
        e = Event(organizer_id=org.id, title="LLM Build Night", category_slug="ai-ml", event_type="workshop", mode="in_person",
                  venue_name="Main Auditorium", address="Gandhipuram, Coimbatore", start_at=start, end_at=start + timedelta(hours=3),
                  fee_inr=fee, capacity=40, status="published", verification_label="organizer_verified", risk_score=0,
                  published_at=utcnow(), description="Bring a laptop. We build a chatbot together.",
                  eligibility={"required_tags": [], "text": "Open to all college students"})
        db.add(e)
        db.flush()
        for email in members:
            u = db.scalar(select(User).where(User.email == email))
            u.created_at = utcnow() - timedelta(days=60)
            db.add(Registration(user_id=u.id, event_id=e.id, status="registered"))
        db.commit()
        return e.id


def test_rule_answers_come_from_the_event_details(client):
    eid = _event()
    r = client.post(f"/api/events/{eid}/ask", json={"question": "How much does it cost?"}).json()
    assert r["found"] and "₹150" in r["answer"] and r["source"] == "rules" and r["ask"] == "organizer"
    r = client.post(f"/api/events/{eid}/ask", json={"question": "where is it?"}).json()
    assert "Main Auditorium" in r["answer"]
    r = client.post(f"/api/events/{eid}/ask", json={"question": "Is it open to first years?"}).json()
    assert "Open to all college students" in r["answer"]
    r = client.post(f"/api/events/{eid}/ask", json={"question": "Will there be pizza?"}).json()
    assert not r["found"] and r["answer"] == assist.NOT_IN_DETAILS


def test_members_are_pointed_to_the_group_chat(client):
    eid = _event()
    login(client, "student")
    assert client.post(f"/api/events/{eid}/ask", json={"question": "pizza?"}).json()["ask"] == "chat"


def test_ai_answer_is_used_and_not_found_never_guesses(client):
    eid = _event()
    with patch.object(assist.llm, "chat_json", return_value={"found": True, "answer": "Yes, bring a laptop."}) as m:
        r = client.post(f"/api/events/{eid}/ask", json={"question": "Do I need a laptop?"}).json()
    assert r == {"answer": "Yes, bring a laptop.", "found": True, "source": "ai", "ask": "organizer"}
    sent = m.call_args.args[1]
    assert "Bring a laptop" in sent and "@" not in sent  # only event details, no personal data
    with patch.object(assist.llm, "chat_json", return_value={"found": False, "answer": "Probably pizza"}):
        r = client.post(f"/api/events/{eid}/ask", json={"question": "Food?"}).json()
    assert r["answer"] == assist.NOT_IN_DETAILS and not r["found"]


def test_ask_only_for_published_events(client):
    eid = _event()
    with SessionLocal() as db:
        db.get(Event, eid).status = "draft"
        db.commit()
    assert client.post(f"/api/events/{eid}/ask", json={"question": "when?"}).status_code == 404


def _say(eid, email, body, ago_min):
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        db.add(ChatMessage(event_id=eid, sender_id=uid, body=body, created_at=utcnow() - timedelta(minutes=ago_min)))
        db.commit()


def test_rule_summary_lists_unanswered_questions(client):
    eid = _event(members=(ASHA, S1))
    _say(eid, ASHA, "Is parking available?", 50)
    _say(eid, "club@example.com", "Yes, near gate 2.", 40)
    _say(eid, S1, "Can I bring a friend? call 9876543210", 30)
    _say(eid, ASHA, "See you all", 20)
    login(client, "student")
    assert client.get(f"/api/events/{eid}/chat/summary").status_code == 403
    login(client, "organizer")
    r = client.get(f"/api/events/{eid}/chat/summary").json()
    assert r["messages"] == 3 and r["source"] == "rules"
    assert r["questions"] == ["Can I bring a friend? call [hidden]"]


def test_ai_summary_gets_no_names_or_numbers(client):
    eid = _event(members=(ASHA,))
    _say(eid, ASHA, "Mail me at asha@example.com about the slides?", 10)
    with SessionLocal() as db, patch.object(assist.llm, "chat_json", return_value={"summary": ["People asked about slides."], "questions": ["Slides?"]}) as m:
        r = assist.summarize(db, db.get(Event, eid))
    sent = m.call_args.args[1]
    assert "Asha" not in sent and "asha@example.com" not in sent and sent.startswith("S1:")
    assert r["source"] == "ai" and r["summary"] == ["People asked about slides."]


def test_daily_summary_alert_once_after_8pm(client):
    eid = _event(members=(ASHA, S1))
    for i, (who, text) in enumerate([(ASHA, "Is lunch provided?"), (S1, "What time do doors open?"), (ASHA, "Thanks!")]):
        _say(eid, who, text, 30 - i)
    now = utcnow()
    evening = now.replace(hour=15, minute=0, second=0, microsecond=0)  # 8:30 PM IST
    if evening < now:
        evening += timedelta(days=1)  # the next one, under a day after the messages
    with SessionLocal() as db:
        assert assist.send_daily_summaries(db, evening - timedelta(hours=2)) == 0  # 6:30 PM IST: too early
        assert assist.send_daily_summaries(db, evening) == 1
        n = db.scalar(select(Notification).where(Notification.type == "chat_summary", Notification.event_id == eid))
        assert n.payload["path"] == f"/event/{eid}/chat" and "questions waiting" in n.body
        assert assist.send_daily_summaries(db, evening + timedelta(minutes=30)) == 0  # once a day
