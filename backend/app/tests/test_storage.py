"""Posters live in the database (a redeploy can't lose them); timetable photos are never stored."""

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import StoredFile

from .conftest import login
from .test_organizer import extract
from .test_timetable import timetable_png


def stored_count() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(StoredFile))


def test_poster_is_kept_in_the_database_and_served(client):
    login(client, "organizer")
    url = extract(client, "ai_workshop")["poster_url"]
    assert url and url.startswith("/api/files/") and stored_count() == 1
    r = client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp" and r.content[:4] == b"RIFF"
    assert client.get("/api/files/../../etc.webp").status_code == 404


def test_timetable_photo_is_not_stored(client):
    login(client, "student")
    client.post("/api/availability/timetable", files={"file": ("it_year3.png", timetable_png("it_year3"), "image/png")})
    assert stored_count() == 0
