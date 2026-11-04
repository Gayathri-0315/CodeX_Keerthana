from .conftest import login
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Event, Notification, Organizer, Registration, User
from app.services import jobs, notify, registration
from app.services.showup_score import expected_turnout, leave_by, likelihood, reminder_times
from app.timeutil import utcnow


# ---- show-up likelihood (5.7) ----

def lk(**kw):
    base = dict(interest=60, distance_km=3, days_before=3, reminder_confirmed=False, past_rate=None, slack_min=60)
    base.update(kw)
    return likelihood(**base).p


def test_likelihood_baseline_and_bounds():
    assert lk() == 0.70
    assert lk(interest=95, reminder_confirmed=True, past_rate=1.0) == 0.95  # capped
    assert lk(distance_km=30, days_before=30, past_rate=0.0, slack_min=0) == 0.30
    assert 0.15 <= lk(distance_km=50, days_before=60, past_rate=0.0, slack_min=0) <= 0.95


@pytest.mark.parametrize("worse,better", [
    (dict(interest=50), dict(interest=90)),
    (dict(distance_km=20), dict(distance_km=10)),
    (dict(distance_km=10), dict(distance_km=5)),
    (dict(days_before=20), dict(days_before=2)),
    (dict(reminder_confirmed=False), dict(reminder_confirmed=True)),
    (dict(past_rate=0.2), dict(past_rate=0.9)),
    (dict(slack_min=10), dict(slack_min=45)),
])
def test_likelihood_is_monotonic(worse, better):
    assert lk(**worse) < lk(**better)


def test_likelihood_reasons_explain_each_adjustment():
    r = likelihood(interest=90, distance_km=12, days_before=3, reminder_confirmed=True, past_rate=None, slack_min=10).reasons
    assert len(r) == 4 and any("km away" in x for x in r)


def test_expected_turnout_range():
    mean, low, high = expected_turnout([0.7] * 20)
    assert mean == 14.0 and low < 14 < high and high <= 20


# ---- leave-by (5.8) ----

def test_leave_by_and_reminder_times():
    start = datetime(2026, 10, 31, 9, 30)  # 3 PM IST
    assert leave_by(start, 19) == start - timedelta(minutes=29)
    times = reminder_times(start, 19)
    assert times["reminder_24h"] == start - timedelta(hours=24)
    assert times["reminder_2h"] == start - timedelta(hours=2)
    assert times["reminder_leave_by"] == start - timedelta(minutes=44)


# ---- registration and waitlist (5.9) ----

def full_event(db):
    return db.scalar(select(Event).where(Event.title == "Startup Pitch Night"))


def student(db, n=None):
    return db.scalar(select(User).where(User.email == ("asha@example.com" if n is None else f"student{n}@example.com")))


def waitlist(db, event):
    return list(db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.status == "waitlisted")
                           .order_by(Registration.waitlist_position)))


def test_register_and_waitlist(client):
    login(client, "student")
    feed = client.get("/api/feed").json()["items"]
    r = client.post(f"/api/events/{feed[0]['id']}/register").json()
    assert r["status"] == "registered" and r["toast"]["title"] == "You're in" and "Leave by" in r["toast"]["body"]
    again = client.post(f"/api/events/{feed[0]['id']}/register").json()
    assert again["id"] == r["id"]  # idempotent
    with SessionLocal() as db:
        event_id = full_event(db).id
    w = client.post(f"/api/events/{event_id}/register").json()
    assert w["status"] == "waitlisted" and w["waitlist_position"] == 4 and w["toast"]["body"].startswith("You're #4")
    assert client.get(f"/api/events/{feed[0]['id']}").json()["registration"]["status"] == "registered"
    mine = client.get("/api/registrations/me").json()
    assert len(mine["upcoming"]) == 1 and len(mine["waitlist"]) == 1


def test_cancel_promotes_exactly_one_and_confirm(client):
    with SessionLocal() as db:
        event = full_event(db)
        first_in_line = waitlist(db, event)[0]
        seat = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.status == "registered"))
        promoted = registration.cancel(db, seat)
        assert [p.id for p in promoted] == [first_in_line.id]
        assert [w.waitlist_position for w in waitlist(db, event)] == [1, 2]
        jobs.offer_seats(db, promoted)
        n = db.scalar(select(Notification).where(Notification.user_id == first_in_line.user_id, Notification.type == "seat_opened"))
        assert n.title == "A seat just opened up"
        assert registration.confirm_seat(db, first_in_line).status == "registered"
        assert registration.seats_taken(db, event.id) == event.capacity


def test_unconfirmed_offer_expires_to_next(client):
    with SessionLocal() as db:
        event = full_event(db)
        line = waitlist(db, event)
        seat = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.status == "registered"))
        registration.cancel(db, seat)
        later = utcnow() + timedelta(minutes=30)
        promoted = registration.expire_offers(db, later)
        assert [p.id for p in promoted] == [line[1].id]
        db.refresh(line[0])
        assert line[0].status == "cancelled"
        with pytest.raises(Exception):
            registration.confirm_seat(db, line[0], later)


def test_concurrent_cancels_never_double_promote(client):
    with SessionLocal() as db:
        event = full_event(db)
        seat_ids = [r.id for r in db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.status == "registered")).all()[:2]]
        event_id, capacity = event.id, event.capacity

    def cancel(rid):
        with SessionLocal() as s:
            registration.cancel(s, s.get(Registration, rid))

    threads = [threading.Thread(target=cancel, args=(rid,)) for rid in seat_ids] + [threading.Thread(target=cancel, args=(seat_ids[0],))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with SessionLocal() as db:
        statuses = [s for (s,) in db.execute(select(Registration.status).where(Registration.event_id == event_id))]
        assert statuses.count("promoted_pending") == 2  # two seats freed, two offers, never more
        assert registration.seats_taken(db, event_id) == capacity


def test_cancel_endpoint_releases_seat(client):
    login(client, "student")
    eid = client.get("/api/feed").json()["items"][0]["id"]
    reg = client.post(f"/api/events/{eid}/register").json()
    assert client.post(f"/api/registrations/{reg['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/registrations/{reg['id']}/cancel").status_code == 409


# ---- notification rules (5.5) ----

def fake_user(**kw):
    base = dict(quiet_hours_start="22:00", quiet_hours_end="07:00", notif_paused_until=None, notif_max_per_week=3)
    base.update(kw)
    return SimpleNamespace(**base)


def test_quiet_hours_wrap_midnight():
    u = fake_user()
    assert notify.in_quiet_hours(u, datetime(2026, 10, 30, 17, 0))  # 22:30 IST
    assert notify.in_quiet_hours(u, datetime(2026, 10, 30, 1, 0))  # 06:30 IST
    assert not notify.in_quiet_hours(u, datetime(2026, 10, 30, 6, 0))  # 11:30 IST
    assert not notify.in_quiet_hours(fake_user(quiet_hours_start="00:00", quiet_hours_end="00:00"), datetime(2026, 10, 30, 17, 0))


def test_pause():
    now = datetime(2026, 10, 30, 6, 0)
    assert notify.is_paused(fake_user(notif_paused_until=now + timedelta(days=1)), now)
    assert not notify.is_paused(fake_user(notif_paused_until=now - timedelta(minutes=1)), now)


def test_weekly_cap_and_urgent_overflow(client):
    with SessionLocal() as db:
        u = student(db)
        now = utcnow()
        events = db.scalars(select(Event).where(Event.status == "published")).unique().all()
        for e in events[:3]:
            db.add(Notification(user_id=u.id, type="match", event_id=e.id, title="t", body="b", channel_sent={"x": 1}))
        db.commit()
        assert not notify.cap_allows(db, u, "match", now)
        assert notify.cap_allows(db, u, "seat_opened", now)  # urgent may go one over
        db.add(Notification(user_id=u.id, type="deadline", event_id=events[3].id, title="t", body="b", channel_sent={"x": 1}))
        db.commit()
        assert not notify.cap_allows(db, u, "deadline", now)


def test_dedupe_per_user_event_type(client):
    with SessionLocal() as db:
        u, e = student(db), db.scalars(select(Event).where(Event.status == "published")).first()
        assert notify.create(db, u, "match", e, "t", "b", push=False) is not None
        assert notify.create(db, u, "match", e, "t", "b", push=False) is None
        assert notify.create(db, u, "deadline", e, "t", "b", push=False) is not None


def test_quiet_hours_hold_then_flush(client):
    with SessionLocal() as db:
        u, e = student(db), db.scalars(select(Event).where(Event.status == "published")).first()
        night = datetime(2026, 10, 30, 17, 0)  # 22:30 IST
        n = notify.create(db, u, "match", e, "t", "b", now=night)
        assert n.channel_sent == {}
        assert notify.flush_pending(db, night + timedelta(minutes=5)) == 0
        n.created_at = utcnow()
        db.commit()
        morning = utcnow().replace(hour=4, minute=0)  # 09:30 IST
        assert notify.flush_pending(db, morning) == 1 and db.get(Notification, n.id).channel_sent


def publish_sample_workshop(db) -> tuple[Event, int]:
    """Publish the AI Workshop sample poster as the trusted club, then send match alerts."""
    import json

    from app.services import listing
    from app.services.extraction import SEED_DIR, resolve_mock_poster
    from app.timeutil import ist_today

    org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
    spec = resolve_mock_poster(json.loads((SEED_DIR / "posters" / "ai_workshop.json").read_text(encoding="utf-8")), ist_today())
    event = Event(organizer_id=org.id, status="draft")
    listing.apply_form(db, event, listing.form_from_extraction(spec, None, "web_upload"))
    db.add(event)
    db.flush()
    assert listing.publish(db, org, event) == "published"  # publishing sends match alerts (inline under tests)
    sent = db.scalar(select(func.count()).select_from(Notification).where(Notification.event_id == event.id,
                                                                         Notification.type == "match"))
    return event, sent


def test_publish_sends_match_alert_to_fitting_student(client):
    with SessionLocal() as db:
        _, notified = publish_sample_workshop(db)
        assert notified >= 1
        n = db.scalar(select(Notification).where(Notification.user_id == student(db).id, Notification.type == "match"))
        assert n.title == "A seat that fits your Saturday" and n.body.startswith("AI Workshop: Prompt to Product, 3:30 to 5:30 PM")
        assert len(n.body) <= 90


def test_unverified_events_never_alert(client):
    with SessionLocal() as db:
        e = db.scalar(select(Event).where(Event.title == "Free Coding Bootcamp"))
        assert notify.suggest(db, e) == 0


def test_reminders_go_out_once(client):
    with SessionLocal() as db:
        u = student(db)
        e = db.scalar(select(Event).where(Event.title == "AI Workshop: Hands-on with LLMs"))
        registration.register(db, u, e, now=e.start_at - timedelta(days=3))
        at = e.start_at - timedelta(minutes=40)  # after leave-by - 15

        def mine():
            return sorted(db.scalars(select(Notification.type).where(Notification.user_id == u.id, Notification.event_id == e.id,
                                                                     Notification.type.like("reminder%"))))

        assert jobs.send_reminders(db, at) > 0  # seeded registrants get theirs too
        assert mine() == ["reminder_24h", "reminder_2h", "reminder_leave_by"]
        assert jobs.send_reminders(db, at) == 0  # nothing twice
        assert mine() == ["reminder_24h", "reminder_2h", "reminder_leave_by"]


# ---- check-in, analytics, closing (5.10) ----

def test_checkin_analytics_and_close(client):
    login(client, "organizer")
    with SessionLocal() as db:
        e = db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))
        regs = db.scalars(select(Registration).where(Registration.event_id == e.id, Registration.status == "registered")).all()
        token, code = regs[0].checkin_token, regs[1].checkin_code
        eid, total = e.id, len(regs)
    first = client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token}).json()
    assert first["status"] == "checked_in" and first["count"] == 1
    assert client.post(f"/api/organizer/events/{eid}/checkin", json={"token": token}).json()["status"] == "already"
    assert client.post(f"/api/organizer/events/{eid}/checkin", json={"token": code.lower()}).json()["count"] == 2
    assert client.post(f"/api/organizer/events/{eid}/checkin", json={"token": "ZZZZZZ"}).status_code == 404
    a = client.get(f"/api/organizer/events/{eid}/analytics").json()
    assert a["registered"] == total and a["actual"] == 2 and a["expected_low"] <= a["expected"] <= a["expected_high"]
    regs_out = client.get(f"/api/organizer/events/{eid}/registrations").json()["registrations"]
    assert regs_out and all("likelihood" not in r and "reasons" not in r for r in regs_out)  # no per-student scores

    with SessionLocal() as db:
        e = db.get(Event, eid)
        org = db.get(Organizer, e.organizer_id)
        before = org.past_events_count
        assert jobs.close_finished(db, e.end_at + timedelta(minutes=1)) >= 1
        statuses = [s for (s,) in db.execute(select(Registration.status).where(Registration.event_id == eid))]
        assert statuses.count("attended") == 2 and statuses.count("no_show") == total - 2
        db.refresh(org)
        assert org.past_events_count >= before + 1


def test_new_organizer_promoted_after_clean_event(client):
    with SessionLocal() as db:
        org = db.scalar(select(Organizer).where(Organizer.org_name == "QuickCareers Hub"))
        e = db.scalar(select(Event).where(Event.title == "Free Coding Bootcamp"))
        s = student(db, 1)
        db.add(Registration(user_id=s.id, event_id=e.id, status="attended"))
        db.commit()
        jobs.close_finished(db, e.end_at + timedelta(minutes=1))
        db.refresh(org)
        assert org.trust_level == "verified"


def test_ics_download(client):
    login(client, "student")
    eid = client.get("/api/feed").json()["items"][0]["id"]
    r = client.get(f"/api/events/{eid}/ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VEVENT" in r.text and "DTSTART:" in r.text and r.text.endswith("END:VCALENDAR\r\n")


def test_released_seat_is_offered_to_first_on_waitlist(client):
    login(client, "student")
    with SessionLocal() as db:
        e, me = full_event(db), student(db)
        for r in waitlist(db, e):
            r.waitlist_position += 1
        db.add(Registration(user_id=me.id, event_id=e.id, status="waitlisted", waitlist_position=1))
        db.commit()
        seat = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.status == "registered").limit(1))
        promoted = registration.cancel(db, seat)
        assert [r.user_id for r in promoted] == [me.id]
        jobs.offer_seats(db, promoted)
    alerts = client.get("/api/notifications").json()
    assert alerts["items"][0]["type"] == "seat_opened" and alerts["unread"] >= 1
    reg_id = alerts["items"][0]["actions"][0]["registration_id"]
    assert client.post(f"/api/registrations/{reg_id}/confirm-seat").json()["status"] == "registered"


def test_cancel_event_notifies_registrants(client):
    login(client, "organizer")
    with SessionLocal() as db:
        e = db.scalar(select(Event).where(Event.title == "Python Meetup Coimbatore"))
        n_regs = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id))
    r = client.post(f"/api/organizer/events/{e.id}/cancel").json()
    assert r["status"] == "cancelled" and r["notified"] == n_regs
