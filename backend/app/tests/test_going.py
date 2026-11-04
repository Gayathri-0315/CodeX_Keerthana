"""Going blocks end to end: register -> busy in the feed -> cancel frees it again (prompt v2, item 5)."""

from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Organizer

from .conftest import login


def overlapping_event(meetup_id: str) -> str:
    with SessionLocal() as db:
        m = db.get(Event, meetup_id)
        org = db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club"))
        e = Event(organizer_id=org.id, title="Python Office Hours", description="Bring your bugs.", category="Workshop",
                  tags=["python"], mode="in_person", venue_name=m.venue_name, lat=m.lat, lng=m.lng,
                  start_at=m.start_at + timedelta(minutes=15), end_at=m.end_at, fee_inr=0, status="published",
                  verification_label="organizer_verified", risk_score=0, published_at=m.published_at)
        db.add(e)
        db.commit()
        return e.id


def ids(client, tab):
    return {i["id"]: i for i in client.get(f"/api/feed?tab={tab}&limit=50").json()["items"]}


def test_registering_makes_that_time_busy_and_cancel_frees_it(client):
    login(client, "student")
    with SessionLocal() as db:
        meetup = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    other = overlapping_event(meetup)
    assert other in ids(client, "for_you")

    reg = client.post(f"/api/events/{meetup}/register").json()
    assert reg["status"] == "registered"
    assert other not in ids(client, "for_you") and meetup in ids(client, "for_you")
    almost = ids(client, "almost")
    assert almost[other]["clash"] == "You're already going to Python Meetup Coimbatore."

    client.post(f"/api/registrations/{reg['id']}/cancel")
    assert other in ids(client, "for_you")


def test_registering_never_downloads_a_file(client):
    login(client, "student")
    with SessionLocal() as db:
        meetup = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    r = client.post(f"/api/events/{meetup}/register")
    assert r.headers["content-type"].startswith("application/json") and "content-disposition" not in r.headers
