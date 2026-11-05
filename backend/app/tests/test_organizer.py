from .conftest import login, PASSWORD
from app.db import SessionLocal
from app.models import Event, Organizer
from app.seed.make_samples import POSTERS


def poster_bytes(name: str) -> bytes:
    return (POSTERS / "generated" / f"{name}.png").read_bytes()


def extract(client, name: str, filename: str | None = None):
    r = client.post("/api/organizer/events/extract", files={"file": (filename or f"{name}.png", poster_bytes(name), "image/png")})
    assert r.status_code == 200, r.text
    return r.json()


def form_from(fields: dict, poster_url: str | None) -> dict:
    keys = ["title", "description", "category", "category_slug", "tags", "date", "start_time", "end_time", "mode", "venue_name",
            "address", "fee_inr", "registration_deadline", "eligibility_text", "eligibility_tags", "registration_url"]
    form = {k: fields[k] for k in keys if fields.get(k) is not None}
    return {**form, "poster_url": poster_url, "source": "web_upload", "field_confidence": fields["field_confidence"]}


def test_seeded_copy_is_flagged_as_duplicate(client):
    with SessionLocal() as db:
        copy = db.query(Event).filter(Event.status == "pending_review", Event.title.like("AI Workshop%")).one()
        original = db.query(Event).filter(Event.status == "published", Event.title == copy.title).one()
        assert copy.duplicate_of == original.id
        assert any("copy of" in r for r in copy.risk_reasons)
        assert original.duplicate_of is None


def test_students_cannot_use_organizer_routes(client):
    login(client, "student")
    assert client.get("/api/organizer/events").status_code == 403


def test_real_poster_extracts_and_publishes(client):
    login(client, "organizer")
    result = extract(client, "ai_workshop")
    assert result["fields"]["title"] == "AI Workshop: Prompt to Product"
    assert "end_time" in result["low_confidence"] and result["poster_url"].startswith("/api/files/")
    assert client.get(result["poster_url"]).status_code == 200

    form = form_from(result["fields"], result["poster_url"])
    preview = client.post("/api/organizer/events/preview", json=form).json()
    assert preview["risk"]["level"] == "low" and preview["outcome"]["status"] == "published"
    assert preview["reach"]["ready"] and preview["reach"]["count"] >= 1  # the sample student fits

    saved = client.post("/api/organizer/events", json=form).json()
    assert saved["status"] == "draft"
    published = client.post(f"/api/organizer/events/{saved['id']}/publish").json()
    assert published["status"] == "published" and published["verification_label"] == "organizer_verified"

    client.post("/api/auth/logout")
    login(client, "student")
    titles = [e["title"] for e in client.get("/api/feed").json()["items"]]
    assert "AI Workshop: Prompt to Product" in titles


def test_fake_internship_poster_is_blocked_with_reasons(client):
    login(client, "organizer")
    result = extract(client, "fake_internship")
    form = form_from(result["fields"], result["poster_url"])
    saved = client.post("/api/organizer/events", json=form).json()
    published = client.post(f"/api/organizer/events/{saved['id']}/publish").json()
    assert published["status"] == "blocked"
    reasons = " ".join(published["risk"]["reasons"])
    assert "guaranteed internship" in reasons and "UPI" in reasons and "shortener" in reasons

    appeal = client.post(f"/api/organizer/events/{saved['id']}/appeal", json={"note": "This is a real partner company."}).json()
    assert appeal["status"] == "pending_review"


def test_unknown_upload_in_mock_mode_opens_manual_form(client):
    login(client, "organizer")
    r = client.post("/api/organizer/events/extract", files={"file": ("mine.png", _tiny_png(), "image/png")}).json()
    assert r["fields"]["title"] is None and "Fill in the details" in r["message"]


def test_rejects_non_images(client):
    login(client, "organizer")
    r = client.post("/api/organizer/events/extract", files={"file": ("x.txt", b"hello world", "text/plain")})
    assert r.status_code == 415 and r.json()["error"]["message"].startswith("Upload a PNG")


def test_publish_requires_essentials(client):
    login(client, "organizer")
    saved = client.post("/api/organizer/events", json={"title": "Untitled jam"}).json()
    r = client.post(f"/api/organizer/events/{saved['id']}/publish")
    assert r.status_code == 422 and "date" in r.json()["error"]["message"]


def test_new_organizer_goes_to_review_and_admin_approves(client):
    login(client, "organizer")
    form = form_from(extract(client, "flutter_study_jam")["fields"], None)
    client.post("/api/auth/logout")

    with SessionLocal() as db:  # a brand-new club with no published events yet
        from app.models import User
        from app.security import hash_password

        u = User(email="newclub@gmail.com", name="New club", password_hash=hash_password("longenough"), role="organizer",
                 onboarded=True)
        db.add(u)
        db.flush()
        db.add(Organizer(user_id=u.id, org_name="Brand New Club", org_email_domain="gmail.com", trust_level="new"))
        db.commit()
    client.post("/api/auth/login", json={"email": "newclub@gmail.com", "password": "longenough"})
    saved = client.post("/api/organizer/events", json=form).json()
    assert client.post(f"/api/organizer/events/{saved['id']}/publish").json()["status"] == "pending_review"
    client.post("/api/auth/logout")

    login(client, "admin")
    queue = client.get("/api/admin/review-queue").json()["items"]
    assert saved["id"] in [i["id"] for i in queue]
    assert client.post(f"/api/admin/events/{saved['id']}/approve").json()["status"] == "published"
    with SessionLocal() as db:
        e = db.get(Event, saved["id"])
        assert e.status == "published" and e.verification_label == "details_reviewed"
        org_id = e.organizer_id
    assert client.post(f"/api/admin/organizers/{org_id}/verify").json()["trust_level"] == "verified"
    with SessionLocal() as db:
        assert db.get(Organizer, org_id).trust_level == "verified"


def test_three_reports_hide_an_event(client):
    login(client, "student")
    event_id = client.get("/api/feed").json()["items"][0]["id"]
    client.post("/api/auth/logout")
    for i in (1, 2, 3):
        client.post("/api/auth/login", json={"email": f"student{i}@example.com", "password": PASSWORD})
        assert client.post(f"/api/events/{event_id}/report", json={"reason": "Looks fake"}).status_code == 204
        client.post(f"/api/events/{event_id}/report", json={"reason": "Again"})  # repeat reports don't count twice
        client.post("/api/auth/logout")
    with SessionLocal() as db:
        assert db.get(Event, event_id).status == "pending_review"


def _tiny_png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    return buf.getvalue()
