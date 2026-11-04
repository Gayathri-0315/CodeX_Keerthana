from .conftest import login
from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Notification, Registration, User
from app.services import jobs, together
from app.services.showup_score import likelihood


def event_id(title="Python Meetup Coimbatore"):
    with SessionLocal() as db:
        return db.scalar(select(Event.id).where(Event.title == title))


def free_student(eid):
    """A generated student who isn't registered for this event yet."""
    with SessionLocal() as db:
        taken = set(db.scalars(select(Registration.user_id).where(Registration.event_id == eid)))
        return next(u.email for u in db.scalars(select(User).where(User.email.like("student%@example.com"))) if u.id not in taken)


def invite_for_sample_student(client, eid):
    login(client, "asha@example.com")
    reg = client.post(f"/api/events/{eid}/register").json()
    inv = client.post(f"/api/registrations/{reg['id']}/invite").json()
    assert len(inv["code"]) == 8 and inv["url"].endswith(f"/invite/{inv['code']}")
    return reg, inv


def test_invite_accept_pairs_registrations_and_notifies(client):
    eid = event_id()
    reg, inv = invite_for_sample_student(client, eid)
    again = client.post(f"/api/registrations/{reg['id']}/invite").json()
    assert again["code"] == inv["code"]  # one link per registration

    client.post("/api/auth/logout")
    info = client.get(f"/api/invites/{inv['code']}").json()  # public: friends open it before signing in
    assert info["inviter"] == "Asha" and info["going"] == 1 and info["problem"] is None

    friend = free_student(eid)
    login(client, friend)
    r = client.post(f"/api/invites/{inv['code'].lower()}/accept").json()  # codes are case-insensitive
    assert r["status"] == "registered" and [c["name"] for c in r["companions"]] == ["Asha"]
    assert r["toast"]["title"] == "You're going with Asha"

    login(client, "asha@example.com")
    alerts = client.get("/api/notifications").json()["items"]
    assert alerts[0]["type"] == "buddy_joined" and alerts[0]["title"].endswith("is going with you")
    detail = client.get(f"/api/events/{eid}").json()
    assert len(detail["companions"]) == 1
    assert client.get(f"/api/invites/{inv['code']}").json()["going"] == 2


def test_own_invite_and_bad_codes(client):
    eid = event_id()
    _, inv = invite_for_sample_student(client, eid)
    r = client.post(f"/api/invites/{inv['code']}/accept")
    assert r.status_code == 409 and "own invite" in r.json()["error"]["message"]
    assert client.get("/api/invites/NOPE1234").status_code == 404


def test_cancel_tells_the_group_and_invite_goes_stale(client):
    eid = event_id()
    reg, inv = invite_for_sample_student(client, eid)
    login(client, free_student(eid))
    friend_reg = client.post(f"/api/invites/{inv['code']}/accept").json()
    client.post(f"/api/registrations/{friend_reg['id']}/cancel")

    login(client, "asha@example.com")
    alert = client.get("/api/notifications").json()["items"][0]
    assert alert["type"] == "buddy_cancelled" and alert["body"].endswith("You're still going.")
    assert client.get(f"/api/events/{eid}").json()["companions"] == []

    client.post(f"/api/registrations/{reg['id']}/cancel")
    assert client.get(f"/api/invites/{inv['code']}").json()["problem"] == "Asha isn't going anymore."


def test_going_with_a_friend_raises_likelihood():
    base = dict(interest=60, distance_km=3, days_before=3, reminder_confirmed=False, past_rate=None, slack_min=60)
    assert round(likelihood(**base, with_friend=True).p - likelihood(**base).p, 2) == 0.10
    assert "Going with a friend (+10%)" in likelihood(**base, with_friend=True).reasons


def test_reminder_names_the_friend(client):
    eid = event_id("AI Workshop: Hands-on with LLMs")
    _, inv = invite_for_sample_student(client, eid)
    login(client, free_student(eid))
    client.post(f"/api/invites/{inv['code']}/accept")
    with SessionLocal() as db:
        e = db.get(Event, eid)
        jobs.send_reminders(db, e.start_at - timedelta(minutes=40))
        asha = db.scalar(select(User).where(User.email == "asha@example.com"))
        n = db.scalar(select(Notification).where(Notification.user_id == asha.id, Notification.type == "reminder_leave_by"))
        assert "is going too." in n.body and len(n.body) <= 90


def test_classmates_going_is_a_count_not_names(client):
    login(client, "asha@example.com")
    items = client.get("/api/feed").json()["items"]
    with SessionLocal() as db:
        asha = db.scalar(select(User).where(User.email == "asha@example.com"))
        counts = together.classmates_going(db, asha, [i["id"] for i in items])
    for i in items:
        expected = counts.get(i["id"])
        assert i["classmates_going"] == expected
        if expected:
            assert expected["label"] == "IT, year 3" and set(expected) == {"count", "label"}


def test_friend_joins_and_leave_by_names_them(client):
    eid = event_id()
    login(client, "asha@example.com")
    client.post(f"/api/events/{eid}/register")
    with SessionLocal() as db:
        reg = db.scalar(select(Registration).join(User, User.id == Registration.user_id)
                        .where(Registration.event_id == eid, User.email == "asha@example.com"))
        friend = db.scalar(select(User).where(User.email == free_student(eid)))
        together.accept(db, friend, together.create_invite(db, reg).code)
        name = together.first_name(friend)
        event = db.get(Event, eid)
        reg = db.get(Registration, reg.id)
        assert jobs.send_reminders(db, event.start_at - timedelta(minutes=5)) > 0
    items = client.get("/api/notifications").json()["items"]
    assert any(i["title"] == f"{name} is going with you" for i in items)
    leave = next(i for i in items if i["type"] == "reminder_leave_by")
    assert leave["body"].endswith(f"{name} is going too.")
