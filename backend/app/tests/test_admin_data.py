"""Admins can see every event's registrants with their details, students and organizers. Nobody else can."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event

from .conftest import login


def _pitch_night_id():
    with SessionLocal() as db:
        return db.scalar(select(Event.id).where(Event.title == "Startup Pitch Night"))


def test_admin_sees_who_registered_with_details(client):
    login(client, "admin")
    events = client.get("/api/admin/events", params={"q": "pitch"}).json()["items"]
    ev = next(e for e in events if e["title"] == "Startup Pitch Night")
    assert ev["registered"] == 20 and ev["waitlisted"] > 0 and ev["organizer"] == "Coimbatore AI Club"
    people = client.get(f"/api/admin/events/{ev['id']}/people").json()
    regs = people["registrations"]
    assert len(regs) == 20 + ev["waitlisted"] and sum(r["status"] == "waitlisted" for r in regs) == ev["waitlisted"]
    p = regs[0]
    assert p["email"].endswith("@example.com") and p["name"] and p["department"] and {"college", "year", "interests", "home_area"} <= p.keys()


def test_admin_students_and_organizers(client):
    login(client, "admin")
    studs = client.get("/api/admin/students", params={"q": "asha"}).json()["items"]
    assert studs and studs[0]["email"] == "asha@example.com"
    one = client.get(f"/api/admin/students/{studs[0]['id']}").json()
    assert one["college"] == "Sample College of Technology" and one["interests"][0] == "ai" and "history" in one
    orgs = client.get("/api/admin/organizers", params={"q": "coimbatore ai"}).json()["items"]
    org = client.get(f"/api/admin/organizers/{orgs[0]['id']}").json()
    assert org["email"] == "club@example.com" and org["events"] and any(e["registered"] for e in org["events"])
    assert len(client.get("/api/admin/events", params={"when": "all"}).json()["items"]) >= 25


def test_only_admins(client):
    eid = _pitch_night_id()
    for role in ("student", "organizer"):
        login(client, role)
        for path in ("/api/admin/events", f"/api/admin/events/{eid}/people", "/api/admin/students"):
            assert client.get(path).status_code == 403, (role, path)
    client.cookies.clear()
    assert client.get(f"/api/admin/events/{eid}/people").status_code in (401, 403)


def test_lists_understand_sentences(client):
    login(client, "admin")
    studs = client.get("/api/admin/students", params={"q": "3rd year IT students from sample college"}).json()
    assert studs["terms"] and any(s["email"] == "asha@example.com" for s in studs["items"])
    assert all(s["year"] == "Year 3" and s["department"] == "IT" for s in studs["items"])
    orgs = client.get("/api/admin/organizers", params={"q": "show me unverified organizers"}).json()["items"]
    assert orgs and all(o["trust_level"] == "new" for o in orgs)
    evs = client.get("/api/admin/events", params={"q": "free hackathons by coimbatore ai club", "when": "all"}).json()["items"]
    assert any(e["title"] == "ML Hackathon: Build for Kovai" for e in evs) and all(e["fee_inr"] == 0 for e in evs)


def test_terms_never_include_filler_and_short_words_are_whole_words():
    from app.services import smart_find as sf

    assert sf.rule_terms("show me final year CSE students who checked in") == ["year 4", "cse", "attended"]
    assert not sf.matches(sf.text_of("Aishwarya"), ["ai"]) and sf.matches(sf.text_of("ai-ml"), ["ai"])
    assert not sf.matches(sf.text_of("new"), ["verified"])
