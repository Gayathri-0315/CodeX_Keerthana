"""Run Alembic migrations from code (startup and manage.py)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import BACKEND_DIR
from .db import engine


def alembic_config() -> Config:
    return Config(str(Path(BACKEND_DIR) / "alembic.ini"))


def upgrade() -> None:
    tables = set(inspect(engine).get_table_names())
    if "users" in tables and "alembic_version" not in tables:
        raise SystemExit(
            "This database was created before migrations existed. If it only holds local test data, run "
            "`npm run seed` (python manage.py seed_dev) to recreate it."
        )
    command.upgrade(alembic_config(), "head")
