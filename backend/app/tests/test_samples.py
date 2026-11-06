"""Sample data for a live site: added next to real data, removable, and nobody can sign in to it."""

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Event, Organizer, User
from app.seed import seed as seed_mod
from app.security import hash_password


def _count(model):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_load_and_remove_samples_keep_real_data(client):
    seed_mod.remove_samples()  # start like a live site: no samples
    assert _count(Event) == 0
    with SessionLocal() as db:  # real people already on the site
        db.add(User(email="real.student@gmail.com", name="Real", role="student", password_hash=hash_password("x"), onboarded=True))
        db.add(User(email="boss@college.edu", name="Admin", role="admin", password_hash=hash_password("x"), onboarded=True))
        db.commit()

    r = seed_mod.load_samples()
    assert r["events"] == 25 and _count(Organizer) == 4
    with SessionLocal() as db:
        events = db.scalars(select(Event)).all()
        assert all(e.description.startswith(seed_mod.SAMPLE_NOTE) for e in events)
        assert db.scalar(select(User).where(User.email == "asha@example.com")) is None  # no sign-in demo accounts
        assert db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) == 2  # local + real: no new one
    assert client.get("/api/public/events").status_code == 200
    # The sample accounts' password was random and never shown.
    bad = client.post("/api/auth/login", json={"email": "club@example.com", "password": "localdev-pass-1"})
    assert bad.status_code in (400, 401)
    with pytest.raises(SystemExit):
        seed_mod.load_samples()  # not twice

    out = seed_mod.remove_samples()
    assert out["events"] == 25 and _count(Event) == 0 and _count(Organizer) == 0
    with SessionLocal() as db:
        assert {u.email for u in db.scalars(select(User))} == {"real.student@gmail.com", "boss@college.edu", "admin@example.com"}
