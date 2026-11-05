"""After-event moment (feature 2): organizer-only check-in, the next-day 'How was it?', feedback aggregate."""

from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Feedback, Notification, Registration, User
from app.services import followup
from app.timeutil import ist_to_utc, to_ist

from .conftest import login


def meetup_and_reg(client):
    """Asha registers for the meetup; returns (event_id, registration_id, checkin_token)."""
    login(client, "student")
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    reg = client.post(f"/api/events/{eid}/register").json()
    with SessionLocal() as db:
        token = db.get(Registration, reg["id"]).checkin_token
    return eid, reg["id"], token


def test_students_can_never_check_themselves_in(client):
    eid, rid, token = meetup_and_reg(client)
    assert client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token}).status_code == 403
    with SessionLocal() as db:
        assert db.get(Registration, rid).status == "registered"
    login(client, "organizer")
    assert client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token}).json()["status"] == "checked_in"
    with SessionLocal() as db:
        assert db.get(Registration, rid).status == "attended"


def test_checkin_pushes_the_moment_to_the_student(client, monkeypatch):
    from app.services import stream

    sent = []
    monkeypatch.setattr(stream, "publish", lambda uid, kind, data: sent.append((uid, kind, data)) or True)
    eid, rid, token = meetup_and_reg(client)
    login(client, "organizer")
    client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token})
    with SessionLocal() as db:
        asha = db.scalar(select(User.id).where(User.email == "asha@example.com"))
    assert (asha, "checked_in") in [(u, k) for u, k, _ in sent]


def _morning_after(db, event_id):
    e = db.get(Event, event_id)
    return ist_to_utc(to_ist(e.end_at).date() + timedelta(days=1), 10 * 60 + 5)


def test_how_was_it_goes_only_to_attended_and_once(client):
    eid, rid, token = meetup_and_reg(client)
    login(client, "organizer")
    client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token})
    with SessionLocal() as db:
        when = _morning_after(db, eid)
        seeded = db.scalars(select(Registration).where(Registration.event_id == eid, Registration.id != rid)).all()
        assert all(r.status != "attended" for r in seeded)
        assert followup.send_how_was(db, when - timedelta(hours=3)) == 0  # 7 AM: too early
        assert followup.send_how_was(db, when) == 1  # only the checked-in student
        assert followup.send_how_was(db, when) == 0  # once
        n = db.scalar(select(Notification).where(Notification.type == "how_was"))
        assert n.title == "How was Python Meetup Coimbatore?" and n.payload["registration_id"] == rid
        suggested = n.payload.get("suggested")
        assert suggested and suggested["event_id"] != eid


def test_no_shows_get_nothing(client):
    eid, rid, _ = meetup_and_reg(client)  # registered, never checked in
    with SessionLocal() as db:
        assert followup.send_how_was(db, _morning_after(db, eid)) == 0
    assert client.post(f"/api/registrations/{rid}/feedback", json={"kind": "as_described"}).status_code == 409


def test_feedback_aggregate_hides_individuals(client):
    eid, rid, token = meetup_and_reg(client)
    login(client, "organizer")
    client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token})
    login(client, "student")
    assert client.post(f"/api/registrations/{rid}/feedback", json={"kind": "as_described"}).status_code == 204
    login(client, "organizer")
    a = client.get(f"/api/organizer/events/{eid}/analytics").json()
    assert a["described_pct"] is None and a["described_answers"] == 1  # under 3 answers: no percentage
    regs = client.get(f"/api/organizer/events/{eid}/registrations").json()["registrations"]
    assert all("feedback" not in r and "as_described" not in str(r) for r in regs)
    with SessionLocal() as db:  # two more attended students answer
        for email, kind in (("student1@example.com", "as_described"), ("student2@example.com", "not_as_described")):
            u = db.scalar(select(User).where(User.email == email))
            db.add(Registration(user_id=u.id, event_id=eid, status="attended"))
            db.add(Feedback(user_id=u.id, event_id=eid, kind=kind))
        db.commit()
    a = client.get(f"/api/organizer/events/{eid}/analytics").json()
    assert a["described_answers"] == 3 and a["described_pct"] == 67
