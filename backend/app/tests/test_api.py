def test_demo_login_and_me(client):
    r = client.post("/api/auth/demo", json={"role": "student"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "student@demo.app"


def test_me_requires_auth_with_error_shape(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_session_is_null_when_signed_out(client):
    assert client.get("/api/auth/session").json() == {"user": None}
    client.post("/api/auth/demo", json={"role": "organizer"})
    user = client.get("/api/auth/session").json()["user"]
    assert user["role"] == "organizer" and user["organizer"]["trust_level"] == "trusted"


def test_register_then_login(client):
    r = client.post("/api/auth/register", json={"name": "Ravi", "email": "Ravi@Example.com", "password": "longenough"})
    assert r.status_code == 200 and r.json()["onboarded"] is False
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "longenough"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "wrong-one"}).status_code == 401


def test_seeded_student_feed_matches_phase_3_acceptance(client):
    client.post("/api/auth/demo", json={"role": "student"})
    for_you = client.get("/api/feed").json()["items"]
    titles = [e["title"] for e in for_you]
    assert titles[:2] == ["AI Workshop: Hands-on with LLMs", "Python Meetup Coimbatore"]
    ai = for_you[0]
    assert ai["reasons"][0] == "Fits your Saturday 2 to 6 PM gap"
    assert "Matches your interests in AI and Python" in ai["reasons"]
    almost = {e["title"]: e for e in client.get("/api/feed?tab=almost").json()["items"]}
    assert almost["ML Hackathon: Build for Kovai"]["clash"] == "Runs until 5 PM, you're free until 1 PM on Sunday."
    every = titles + list(almost)
    assert "GUARANTEED INTERNSHIP AT TOP MNC" not in every and "Live Music Evening: Indie Kovai" not in every


def test_feed_pagination(client):
    client.post("/api/auth/demo", json={"role": "student"})
    first = client.get("/api/feed?limit=2").json()
    assert len(first["items"]) == 2 and first["next_cursor"] == "2" and first["total"] == 4
    second = client.get("/api/feed?limit=2&cursor=2").json()
    assert second["next_cursor"] is None and {e["id"] for e in second["items"]}.isdisjoint({e["id"] for e in first["items"]})


def test_save_dismiss_and_undo(client):
    client.post("/api/auth/demo", json={"role": "student"})
    top = client.get("/api/feed").json()["items"][0]
    assert client.post(f"/api/events/{top['id']}/save").status_code == 204
    saved = client.get("/api/feed?tab=saved").json()["items"]
    assert [e["id"] for e in saved] == [top["id"]] and saved[0]["saved"]
    client.delete(f"/api/events/{top['id']}/save")
    assert client.get("/api/feed?tab=saved").json()["total"] == 0

    client.post(f"/api/events/{top['id']}/dismiss")
    assert top["id"] not in [e["id"] for e in client.get("/api/feed").json()["items"]]
    client.delete(f"/api/events/{top['id']}/dismiss")
    assert client.get("/api/feed").json()["items"][0]["id"] == top["id"]


def test_event_detail_and_visibility(client):
    client.post("/api/auth/demo", json={"role": "student"})
    top = client.get("/api/feed").json()["items"][0]
    d = client.get(f"/api/events/{top['id']}").json()
    assert d["organizer"]["trust_label"] == "Trusted organizer" and d["seats_taken"] == 18 and d["maps_url"]
    assert d["why_not"] is None and len(d["reasons"]) >= 4
    from app.db import SessionLocal
    from app.models import Event
    with SessionLocal() as db:
        blocked = db.query(Event).filter(Event.status == "blocked").first().id
    assert client.get(f"/api/events/{blocked}").status_code == 404
    assert client.get("/api/events/nope").json()["error"]["code"] == "not_found"


def test_availability_put_replaces_and_updates_count(client):
    client.post("/api/auth/demo", json={"role": "student"})
    before = client.get("/api/feed/count").json()["fits"]
    r = client.put("/api/availability", json={"slots": [{"day_of_week": d, "start_min": 360, "end_min": 1320} for d in range(7)]})
    assert r.status_code == 200 and len(r.json()["slots"]) == 7
    assert client.get("/api/feed/count").json()["fits"] > before
    client.put("/api/availability", json={"slots": []})
    assert client.get("/api/feed/count").json()["fits"] == 0


def test_availability_rejects_bad_range(client):
    client.post("/api/auth/demo", json={"role": "student"})
    r = client.put("/api/availability", json={"slots": [{"day_of_week": 1, "start_min": 600, "end_min": 600}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid"


def test_patch_profile_interests_export_delete(client):
    client.post("/api/auth/demo", json={"role": "student"})
    assert client.patch("/api/users/me", json={"budget_max_inr": None, "quiet_hours_start": "23:00"}).json()["budget_max_inr"] is None
    assert client.patch("/api/users/me", json={"quiet_hours_start": "25:00"}).status_code == 422
    r = client.put("/api/users/me/interests", json={"interests": [{"tag": "Design", "weight": 3}], "interest_text": "UX"})
    assert [i["tag"] for i in r.json()["interests"]] == ["design"]
    export = client.get("/api/users/me/export").json()
    assert export["profile"]["email"] == "student@demo.app" and len(export["availability"]) == 2
    assert client.delete("/api/users/me").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
