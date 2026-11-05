import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database before anything imports app.config.
_tmp = Path(tempfile.mkdtemp()) / "test.db"
# TEST_DATABASE_URL runs the suite against a real PostgreSQL (it is wiped on every test).
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["AI_MODE"] = "mock"
os.environ["SEED_DEV_PASSWORD"] = "sample-pass-123"
os.environ["EMAIL_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.deps import auth_limit, email_limit, upload_limit  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.seed import reset_and_seed  # noqa: E402

PASSWORD = os.environ["SEED_DEV_PASSWORD"]
ACCOUNTS = {"student": "asha@example.com", "organizer": "club@example.com", "admin": "admin@example.com"}


def with_csrf(c: TestClient) -> TestClient:
    """Act like the web app: every request echoes the current CSRF cookie in the X-CSRF-Token header."""

    def add_header(request):
        token = next((ck.value for ck in c.cookies.jar if ck.name == "showup_csrf"), None)
        if token:
            request.headers["X-CSRF-Token"] = token

    c.event_hooks["request"] = [add_header]
    c.get("/api/auth/session")  # like the app's first call: hands out the CSRF cookie
    return c


def login(c: TestClient, who: str) -> dict:
    """Sign in as a sample account: 'student', 'organizer', 'admin', or an email address."""
    c.post("/api/auth/logout")
    r = c.post("/api/auth/login", json={"email": ACCOUNTS.get(who, who), "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def client():
    reset_and_seed()
    auth_limit.reset()
    email_limit.reset()
    upload_limit.reset()
    with TestClient(app) as c:
        yield with_csrf(c)
