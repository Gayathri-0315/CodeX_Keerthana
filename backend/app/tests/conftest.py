import os
import tempfile
from pathlib import Path

# Point the app at a throwaway database before anything imports app.config.
_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ["AI_MODE"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed.seed import reset_and_seed  # noqa: E402


@pytest.fixture()
def client():
    reset_and_seed()
    with TestClient(app) as c:
        yield c
