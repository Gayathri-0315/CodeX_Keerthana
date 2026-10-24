def test_demo_login_and_me(client):
    r = client.post("/api/auth/demo", json={"role": "student"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "student@demo.app"


def test_me_requires_auth_with_error_shape(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_register_then_login(client):
    r = client.post("/api/auth/register", json={"name": "Ravi", "email": "Ravi@Example.com", "password": "longenough"})
    assert r.status_code == 200 and r.json()["onboarded"] is False
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "longenough"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "ravi@example.com", "password": "wrong-one"}).status_code == 401


def test_seeded_student_fits_expected_events(client):
    client.post("/api/auth/demo", json={"role": "student"})
    events = {e["title"]: e for e in client.get("/api/events").json()["events"]}
    assert events["AI Workshop: Hands-on with LLMs"]["fits"]
    assert events["Python Meetup Coimbatore"]["fits"]
    assert events["ML Hackathon: Build for Kovai"]["almost"]
    assert events["ML Hackathon: Build for Kovai"]["reason"] == "Runs until 5 PM, you're free until 1 PM on Sunday."
    assert "GUARANTEED INTERNSHIP AT TOP MNC" not in events


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
