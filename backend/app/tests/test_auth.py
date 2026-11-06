"""Real auth: sign-up for both roles, email verification, lockout, password reset, CSRF, role checks."""

import re

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Event, User
from app.security import password_problem

from .conftest import PASSWORD, login

STUDENT = {"name": "Ravi", "email": "ravi@example.org", "password": "longenough1"}
ORGANIZER = {"name": "Meena", "org_name": "Robotics Club", "email": "meena@psgtech.ac.in", "password": "longenough1",
             "phone": "+91 98765 43210", "college_or_company": "PSG Tech"}


def latest_link(caplog, kind: str) -> str:
    return re.findall(rf"/{kind}\?token=([\w-]+)", caplog.text)[-1]


def test_student_signup_is_name_email_password_and_can_register_at_once(client, caplog):
    me = client.post("/api/auth/register", json=STUDENT).json()
    assert me["role"] == "student" and me["name"] == "Ravi" and me["email"] == "ravi@example.org"
    assert "email skipped" not in caplog.text  # no verification code is sent
    with SessionLocal() as db:
        eid = db.scalar(select(Event.id).where(Event.title == "Python Meetup Coimbatore"))
    assert client.post(f"/api/events/{eid}/register").json()["status"] == "registered"
    assert client.post("/api/auth/verify", json={"code": "123456"}).status_code in (404, 405)


def test_organizer_signup_starts_new_and_can_publish(client):
    me = client.post("/api/auth/register-organizer", json=ORGANIZER).json()
    assert me["role"] == "organizer" and me["organizer"]["trust_level"] == "new" and me["onboarded"] is True
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == ORGANIZER["email"]))
        assert u.organizer.org_email_domain == "psgtech.ac.in"
    saved = client.post("/api/organizer/events", json={"title": "Robot build night"}).json()
    r = client.post(f"/api/organizer/events/{saved['id']}/publish")
    assert r.status_code == 422  # missing date and venue, not an email check


def test_organizer_signup_needs_only_name_org_email_password(client):
    minimal = {"name": "Meena", "org_name": "Robotics Club", "email": "meena2@example.org", "password": "longenough1"}
    assert client.post("/api/auth/register-organizer", json=minimal).status_code == 200


def test_duplicate_email_and_weak_password(client):
    client.post("/api/auth/register", json=STUDENT)
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json=STUDENT).json()["error"]["code"] == "email_taken"
    weak = {**STUDENT, "email": "x@example.org", "password": "password"}
    assert client.post("/api/auth/register", json=weak).json()["error"]["code"] == "weak_password"


def test_wrong_side_of_the_popup_is_a_clear_error(client):
    r = client.post("/api/auth/login", json={"email": "club@example.com", "password": PASSWORD, "role": "student"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_role" and "organizer account" in r.json()["error"]["message"]


def test_lockout_after_repeated_failures_and_reset_unlocks(client, caplog):
    for _ in range(4):
        assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope-nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope-nope"})
    assert r.status_code == 423 and r.json()["error"]["code"] == "locked"
    # Even the right password is refused while locked.
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD}).json()["error"]["code"] == "locked"

    assert client.post("/api/auth/forgot", json={"email": "asha@example.com"}).status_code == 204
    token = latest_link(caplog, "reset")
    me = client.post("/api/auth/reset", json={"token": token, "password": "a-brand-new-pass"}).json()
    assert me["email"] == "asha@example.com"
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "a-brand-new-pass"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": token, "password": "another-pass-1"}).json()["error"]["code"] == "bad_token"


def test_forgot_does_not_reveal_who_has_an_account(client, caplog):
    assert client.post("/api/auth/forgot", json={"email": "nobody@example.org"}).status_code == 204
    assert "/reset?token=" not in caplog.text


def test_password_reset_signs_out_other_sessions(client, caplog):
    from fastapi.testclient import TestClient

    from app.main import app

    from .conftest import with_csrf

    login(client, "student")
    other = with_csrf(TestClient(app))
    login(other, "student")
    assert other.get("/api/auth/me").status_code == 200
    client.post("/api/auth/forgot", json={"email": "asha@example.com"})
    client.post("/api/auth/reset", json={"token": latest_link(caplog, "reset"), "password": "fresh-password-9"})
    assert other.get("/api/auth/me").status_code == 401  # the old session no longer works
    assert client.get("/api/auth/me").status_code == 200


def test_csrf_is_required_for_cookie_sessions(client):
    login(client, "student")
    client.event_hooks["request"] = []  # stop echoing the token, like a forged cross-site form
    r = client.patch("/api/users/me", json={"name": "Hacked"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf"


def test_session_cookie_is_httponly(client):
    r = client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("showup_session="))
    assert "HttpOnly" in session and "SameSite=lax" in session
    assert not any(c.startswith("showup_csrf=") and "HttpOnly" in c for c in cookies)


@pytest.mark.parametrize("pw,strong,ok", [
    ("short", False, False), ("longenough", False, True), ("password", False, False),
    ("longenough", True, False), ("Str0ng!Passw0rd", True, True),
])
def test_password_rules(pw, strong, ok):
    assert (password_problem(pw, strong) is None) == ok


def test_seed_dev_refuses_in_production(monkeypatch):
    from app.config import settings
    from app.seed import seed

    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(SystemExit):
        seed.reset_and_seed("whatever-pass")



def test_admin_can_sign_in_from_either_side_until_the_admin_page_exists(client):
    for side in ("student", "organizer"):
        r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD, "role": side})
        assert r.status_code == 200 and r.json()["role"] == "admin"
        client.post("/api/auth/logout")


def test_admin_can_reset_their_password_and_each_email_has_its_own_subject(client, caplog):
    assert client.post("/api/auth/forgot", json={"email": "admin@example.com"}).status_code == 204
    assert "Reset your password (" in caplog.text
    me = client.post("/api/auth/reset", json={"token": latest_link(caplog, "reset"), "password": "admin-new-pass-1"}).json()
    assert me["role"] == "admin"
