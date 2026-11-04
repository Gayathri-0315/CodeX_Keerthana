from alembic import context

from app.config import settings
from app.db import Base, engine
import app.models  # noqa: F401  (registers every table on Base.metadata)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=settings.is_sqlite)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        if settings.is_sqlite:
            # SQLite batch migrations copy a table, drop the old one and rename. With foreign keys on, that
            # DROP would cascade and delete every child row (free time, registrations...). Turn them off
            # for the migration; the pragma only works outside a transaction, so set it first.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        # SQLite can't ALTER most things in place; batch mode copies the table instead.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=settings.is_sqlite,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
