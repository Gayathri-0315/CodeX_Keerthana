"""event types

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-05

events.event_type (hackathon, competition, internship, workshop, conference, meetup, webinar, other),
backfilled from each existing event's title, poster category text and tags.
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.event_types import suggest

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_type', sa.String(length=16), nullable=False, server_default='other'))
        batch_op.create_index(batch_op.f('ix_events_event_type'), ['event_type'], unique=False)

    conn = op.get_bind()
    events = sa.table("events", sa.column("id", sa.String), sa.column("title", sa.String), sa.column("category", sa.String),
                      sa.column("tags", sa.JSON), sa.column("event_type", sa.String))
    for row in conn.execute(sa.select(events.c.id, events.c.title, events.c.category, events.c.tags)).all():
        kind = suggest(row.title or "", row.category or "", " ".join(row.tags or []))
        if kind != "other":
            conn.execute(events.update().where(events.c.id == row.id).values(event_type=kind))


def downgrade() -> None:
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_events_event_type'))
        batch_op.drop_column('event_type')
