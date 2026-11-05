"""Event types, opportunity tabs and the stricter internship gate (prompt v2, item 12)."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, Organizer
from app.services import spam
from app.services.event_types import internship_blocks, suggest
from app.timeutil import ist_today

from .conftest import login


def apply_by(days=10) -> str:
    return (ist_today() + timedelta(days=days)).isoformat()


INTERNSHIP = {"title": "Backend Engineering Internship", "description": "Six months, stipend paid monthly. Work on real APIs.",
              "event_type": "internship", "category_slug": "careers", "mode": "online", "registration_deadline": None,
              "registration_url": "https://jobs.example.org/backend-intern", "fee_inr": 0}


def make_org(client, trust: str) -> None:
    login(client, "organizer")
    with SessionLocal() as db:
        db.scalar(select(Organizer).where(Organizer.org_name == "Coimbatore AI Club")).trust_level = trust
        db.commit()


def publish(client, **changes) -> dict:
    form = {**INTERNSHIP, "registration_deadline": apply_by(), **changes}
    saved = client.post("/api/organizer/events", json=form).json()
    return client.post(f"/api/organizer/events/{saved['id']}/publish").json()


@pytest.mark.parametrize("text,kind", [
    ("ML Hackathon", "hackathon"), ("Inter-college Football Cup", "competition"), ("UX Research Internship", "internship"),
    ("Applied AI Summit", "conference"), ("Cloud Basics Live webinar", "webinar"), ("Python Meetup", "meetup"),
    ("Hands-on LLM Workshop", "workshop"), ("Something else", "other"),
])
def test_type_is_suggested(text, kind):
    assert suggest(text) == kind


def test_verified_organizer_publishes_a_clean_internship(client):
    make_org(client, "verified")
    r = publish(client)
    assert r["status"] == "published" and r["verification_label"] == "organizer_verified"
    with SessionLocal() as db:
        e = db.get(Event, r["id"])
        assert e.start_at == e.end_at == e.registration_deadline  # apply-by date, no session time


def test_new_organizers_internship_always_goes_to_review(client):
    make_org(client, "new")
    assert publish(client)["status"] == "pending_review"


@pytest.mark.parametrize("changes,reason", [
    ({"fee_inr": 500}, "can't charge applicants a fee"),
    ({"description": "Pay a refundable security deposit of Rs 2000 to confirm."}, "can't ask applicants for any payment"),
    ({"registration_url": "https://bit.ly/abc123"}, "not a short or look-alike link"),
])
def test_internship_scam_signals_are_blocked_even_for_trusted_organizers(client, changes, reason):
    make_org(client, "trusted")
    r = publish(client, **changes)
    assert r["status"] == "blocked" and any(reason in x for x in r["risk"]["reasons"])


def test_internship_needs_an_apply_link_and_date(client):
    make_org(client, "trusted")
    saved = client.post("/api/organizer/events", json={**INTERNSHIP, "registration_url": None, "registration_deadline": None}).json()
    r = client.post(f"/api/organizer/events/{saved['id']}/publish")
    assert r.status_code == 422 and "an apply-by date" in r.json()["error"]["message"] and "an apply link" in r.json()["error"]["message"]


def test_seeded_fake_internship_is_blocked():
    a = internship_blocks("GUARANTEED INTERNSHIP", "Send Rs 500 registration fee to personal UPI", 500, None)
    assert len(a) == 2
    assert spam.outcome(10, "trusted", "x.com", False, "internship", a)[0] == "blocked"


def test_internships_skip_schedule_never_almost_and_cannot_be_registered(client):
    login(client, "student")
    with SessionLocal() as db:
        intern = db.scalar(select(Event).where(Event.event_type == "internship", Event.status == "published"))
    for_you = client.get("/api/feed?limit=50").json()["items"]
    assert intern.id in [i["id"] for i in for_you]  # no free time needed
    client.put("/api/availability", json={"slots": []})
    assert intern.id not in [i["id"] for i in client.get("/api/feed?tab=almost&limit=50").json()["items"]]
    assert client.post(f"/api/events/{intern.id}/register").status_code == 409


def test_type_tabs_filter_every_list(client):
    login(client, "student")
    for path in ("/api/feed?limit=50&event_type=meetup", "/api/feed/explore?limit=50&event_type=meetup",
                 "/api/public/events?limit=50&event_type=meetup"):
        items = client.get(path).json()["items"]
        assert items and all(i["event_type"] == "meetup" for i in items), path
    assert client.get("/api/feed/explore?event_type=nope").status_code == 422
