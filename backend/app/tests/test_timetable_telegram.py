import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, TelegramLink, User
from app.routers import telegram as tg_router
from app.seed.make_samples import TIMETABLES
from app.services import telegram
from app.services.scheduling import gaps_from_periods


def timetable_png(name: str) -> bytes:
    return (TIMETABLES / "generated" / f"{name}.png").read_bytes()


def test_timetable_import_returns_free_gaps(client):
    client.post("/api/auth/demo", json={"role": "student"})
    r = client.post("/api/availability/timetable", files={"file": ("it_year3.png", timetable_png("it_year3"), "image/png")}).json()
    assert r["message"] is None and len(r["timetable"]["periods"]) == 25
    slots = {(s["day_of_week"], s["start_min"], s["end_min"]) for s in r["free_slots"]}
    # Monday: before class, short break, lunch, and after the lab until 21:00.
    assert {(0, 480, 540), (0, 640, 660), (0, 760, 810), (0, 990, 1260)} <= slots
    assert (6, 480, 1260) in slots  # Sunday is entirely free between 08:00 and 21:00
    # Nothing was saved yet: the student reviews first.
    assert len(client.get("/api/availability").json()["slots"]) == 2


def test_unknown_timetable_in_mock_mode_asks_to_paint(client):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(buf, "PNG")
    client.post("/api/auth/demo", json={"role": "student"})
    r = client.post("/api/availability/timetable", files={"file": ("mine.png", buf.getvalue(), "image/png")}).json()
    assert r["free_slots"] == [] and "Paint your free time" in r["message"]


def test_gap_math_handles_overlaps_and_edges():
    gaps = gaps_from_periods({0: [(470, 540), (530, 600), (1250, 1300)]}, 480, 1260)
    assert gaps[0] == [(600, 1250)]


class FakeTelegram:
    def __init__(self):
        self.sent: list[tuple[str, str, list]] = []
        self.answers: list[str] = []


@pytest.fixture()
def fake_tg(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, "enabled", lambda: True)
    monkeypatch.setattr(telegram, "send", lambda chat, text, buttons=None: fake.sent.append((chat, text, buttons or [])) or True)
    monkeypatch.setattr(telegram, "answer_callback", lambda cid, text: fake.answers.append(text))
    return fake


def link(client, role: str, chat_id: str) -> None:
    client.post("/api/auth/demo", json={"role": role})
    code = client.post("/api/telegram/link-code").json()["code"]
    with SessionLocal() as db:
        tg_router.handle_update(db, {"message": {"chat": {"id": chat_id}, "text": f"/start {code}"}})


def test_link_with_start_code(client, fake_tg):
    link(client, "student", "111")
    me = client.get("/api/auth/me").json()
    assert me["telegram_linked"] and me["notif_channels"]["telegram"]
    assert "You're linked" in fake_tg.sent[-1][1]
    with SessionLocal() as db:
        assert db.scalar(select(TelegramLink)) is None  # codes are single-use


def test_organizer_posts_poster_by_telegram_and_publishes(client, fake_tg, monkeypatch):
    from app.seed.make_samples import POSTERS

    link(client, "organizer", "222")
    monkeypatch.setattr(telegram, "download", lambda file_id: (POSTERS / "generated" / "flutter_study_jam.png").read_bytes())
    with SessionLocal() as db:
        tg_router.handle_update(db, {"message": {"chat": {"id": "222"}, "document": {"file_id": "x", "file_name": "flutter_study_jam.png"}}})
    summary, buttons = fake_tg.sent[-1][1], fake_tg.sent[-1][2]
    assert "Flutter Study Jam" in summary and "Trust check: Looks good" in summary
    pub = next(b["callback_data"] for b in buttons if b.get("callback_data", "").startswith("pub:"))
    assert any(b.get("url", "").endswith("/edit") for b in buttons)

    with SessionLocal() as db:
        tg_router.handle_update(db, {"callback_query": {"id": "cb", "data": pub, "message": {"chat": {"id": "222"}}}})
        event = db.get(Event, pub.split(":")[1])
        assert event.status == "published" and event.source == "telegram"
    assert fake_tg.answers[-1].startswith("Published")


def test_telegram_draft_can_be_cancelled(client, fake_tg, monkeypatch):
    from app.seed.make_samples import POSTERS

    link(client, "organizer", "333")
    monkeypatch.setattr(telegram, "download", lambda file_id: (POSTERS / "generated" / "drone_workshop.png").read_bytes())
    with SessionLocal() as db:
        tg_router.handle_update(db, {"message": {"chat": {"id": "333"}, "document": {"file_id": "x", "file_name": "drone_workshop.png"}}})
    cancel = next(b["callback_data"] for b in fake_tg.sent[-1][2] if b.get("callback_data", "").startswith("del:"))
    with SessionLocal() as db:
        tg_router.handle_update(db, {"callback_query": {"id": "cb", "data": cancel, "message": {"chat": {"id": "333"}}}})
        assert db.get(Event, cancel.split(":")[1]) is None


def test_students_cannot_post_posters(client, fake_tg):
    link(client, "student", "444")
    with SessionLocal() as db:
        tg_router.handle_update(db, {"message": {"chat": {"id": "444"}, "photo": [{"file_id": "x"}]}})
    assert "Only linked organizer accounts" in fake_tg.sent[-1][1]


def test_student_registers_from_alert_button(client, fake_tg):
    link(client, "student", "555")
    eid = client.get("/api/feed").json()["items"][0]["id"]
    with SessionLocal() as db:
        tg_router.handle_update(db, {"callback_query": {"id": "cb", "data": f"reg:{eid}", "message": {"chat": {"id": "555"}}}})
        user = db.scalar(select(User).where(User.telegram_chat_id == "555"))
    assert fake_tg.answers[-1] == "You're in!"
    assert client.get(f"/api/events/{eid}").json()["registration"]["status"] == "registered"
    assert user is not None
