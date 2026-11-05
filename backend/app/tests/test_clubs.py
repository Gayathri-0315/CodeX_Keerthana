"""Club pages and follow (feature 5)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Event, Follow, Notification, Organizer, User
from app.services import clubs
from app.timeutil import utcnow

from .conftest import login

SLUG = "coimbatore-ai-club"


def test_club_page_is_public_and_has_no_student_data(client):
    r = client.get(f"/api/public/clubs/{SLUG}").json()
    assert r["name"] == "Coimbatore AI Club" and r["trust_label"] == "Trusted" and r["upcoming"]
    assert r["followers"] == 0 and r["following"] is False
    assert r["events_hosted"] is not None  # 9 past events: enough to show stats
    text = str(r)
    assert "@example.com" not in text and "registered" not in text
    assert client.get("/api/public/clubs/no-such-club").status_code == 404


def test_stats_hidden_below_three_completed_events(client):
    r = client.get("/api/public/clubs/quickcareers-hub").json()  # a new club
    assert r["events_hosted"] is None and r["attendance_rate"] is None


def test_follow_is_one_unique_pair_and_unfollow_is_one_tap(client):
    login(client, "student")
    assert client.post(f"/api/clubs/{SLUG}/follow").json() == {"following": True, "followers": 1}
    assert client.post(f"/api/clubs/{SLUG}/follow").json()["followers"] == 1  # still one
    assert client.get(f"/api/public/clubs/{SLUG}").json()["following"] is True
    assert [c["slug"] for c in client.get("/api/me/following").json()["items"]] == [SLUG]
    assert client.delete(f"/api/clubs/{SLUG}/follow").json() == {"following": False, "followers": 0}


def test_guests_and_organizers_cannot_follow(client):
    assert client.post(f"/api/clubs/{SLUG}/follow").status_code == 401
    login(client, "organizer")
    assert client.post(f"/api/clubs/{SLUG}/follow").status_code == 403


def test_organizers_see_only_the_count(client):
    login(client, "student")
    client.post(f"/api/clubs/{SLUG}/follow")
    login(client, "organizer")
    s = client.get("/api/organizer/summary").json()
    assert s["followers"] == 1 and s["follower_growth"][-1] == 1
    assert "asha" not in str(s).lower()
    assert client.get("/api/me/following").status_code == 403


def _new_event(db, **kw) -> Event:
    org = db.scalar(select(Organizer).where(Organizer.slug == SLUG))
    start = utcnow() + timedelta(days=9)
    e = Event(organizer_id=org.id, title="Fresh Club Workshop", category_slug="ai-ml", event_type="workshop", mode="online",
              start_at=start, end_at=start + timedelta(hours=2), fee_inr=0, status="published",
              verification_label="organizer_verified", risk_score=0, published_at=utcnow(), **kw)
    db.add(e)
    db.commit()
    return e


def _asha(db):
    u = db.scalar(select(User).where(User.email == "asha@example.com"))
    u.quiet_hours_start = u.quiet_hours_end = "00:00"
    db.commit()
    return u


def test_followers_get_one_alert_for_a_clean_new_event(client):
    login(client, "student")
    client.post(f"/api/clubs/{SLUG}/follow")
    with SessionLocal() as db:
        _asha(db)
        e = _new_event(db)
        assert clubs.notify_followers(db, e) == 1
        assert clubs.notify_followers(db, e) == 0  # dedupe
        n = db.scalar(select(Notification).where(Notification.type == "club_post"))
        assert n.title == "Coimbatore AI Club just posted: Fresh Club Workshop"


def test_flagged_or_blocked_events_never_notify(client):
    login(client, "student")
    client.post(f"/api/clubs/{SLUG}/follow")
    with SessionLocal() as db:
        _asha(db)
        risky = _new_event(db, )
        risky.risk_score, risky.verification_label = 45, "unverified"
        db.commit()
        assert clubs.notify_followers(db, risky) == 0
        blocked = _new_event(db)
        blocked.status = "blocked"
        db.commit()
        assert clubs.notify_followers(db, blocked) == 0


def test_caps_toggle_and_quiet_hours(client):
    login(client, "student")
    client.post(f"/api/clubs/{SLUG}/follow")
    with SessionLocal() as db:
        u = _asha(db)
        u.follow_updates = False
        db.commit()
        assert clubs.notify_followers(db, _new_event(db)) == 0  # switched off
        u.follow_updates, u.notif_max_per_week = True, 1
        db.add(Notification(user_id=u.id, type="match", title="t", body="b"))
        db.commit()
        assert clubs.notify_followers(db, _new_event(db)) == 0  # weekly cap used up
        u.notif_max_per_week = 5
        u.quiet_hours_start, u.quiet_hours_end = "00:00", "23:59"
        db.commit()
        e = _new_event(db)
        assert clubs.notify_followers(db, e) == 1  # stored...
        n = db.scalar(select(Notification).where(Notification.type == "club_post", Notification.event_id == e.id))
        assert not n.channel_sent  # ...but held until quiet hours end


def test_following_filter_on_explore(client):
    login(client, "student")
    assert client.get("/api/feed/explore?following=true").json()["items"] == []
    client.post(f"/api/clubs/{SLUG}/follow")
    items = client.get("/api/feed/explore?following=true&limit=50").json()["items"]
    assert items and {i["organizer_slug"] for i in items} == {SLUG}


def test_follow_toggle_setting(client):
    login(client, "student")
    assert client.patch("/api/users/me", json={"follow_updates": False}).json()["follow_updates"] is False
