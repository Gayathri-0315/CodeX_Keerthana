from alembic import context
from sqlalchemy import create_engine, event

from app.config import settings
from app.db import Base, engine
import app.models  # noqa: F401  (registers every table on Base.metadata)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=settings.is_sqlite)
    with context.begin_transaction():
        context.run_migrations()


def sqlite_migration_engine():
    """SQLite with real transactions, so a migration that fails part-way leaves nothing behind.

    Python's sqlite3 driver doesn't wrap DDL in a transaction by default; this takes over BEGIN.
    Foreign keys are off: batch migrations copy a table, drop the old one and rename, and with foreign
    keys on that DROP would cascade and delete every child row (free time, registrations...).
    """
    eng = create_engine(settings.database_url)

    @event.listens_for(eng, "connect")
    def _connect(dbapi_conn, _record):
        dbapi_conn.isolation_level = None
        dbapi_conn.execute("PRAGMA foreign_keys=OFF")

    @event.listens_for(eng, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return eng


def run_migrations_online() -> None:
    eng = sqlite_migration_engine() if settings.is_sqlite else engine
    with eng.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=settings.is_sqlite,
                          compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    if eng is not engine:
        eng.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
