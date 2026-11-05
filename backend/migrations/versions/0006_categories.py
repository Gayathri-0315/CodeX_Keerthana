"""categories

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05

Adds the fixed category list (with its rows, so production has them too) and events.category_slug,
backfilled from each existing event's tags.
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

FK = "fk_events_category_slug_categories"


def upgrade() -> None:
    from app.services.categories import CATEGORIES, suggest

    categories = op.create_table(
        'categories',
        sa.Column('slug', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('emoji', sa.String(length=16), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('slug'),
    )
    op.bulk_insert(categories, [{"slug": s, "name": n, "emoji": e, "sort_order": i} for i, (s, n, e) in enumerate(CATEGORIES)])
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_slug', sa.String(length=40), nullable=True))
        batch_op.create_index(batch_op.f('ix_events_category_slug'), ['category_slug'], unique=False)
        batch_op.create_foreign_key(FK, 'categories', ['category_slug'], ['slug'], ondelete='SET NULL')

    # Backfill existing events from their tags (production starts empty, so this matters only locally).
    conn = op.get_bind()
    events = sa.table("events", sa.column("id", sa.String), sa.column("tags", sa.JSON), sa.column("title", sa.String),
                      sa.column("category_slug", sa.String))
    for row in conn.execute(sa.select(events.c.id, events.c.tags, events.c.title)).all():
        slug = suggest(row.tags, row.title)
        if slug:
            conn.execute(events.update().where(events.c.id == row.id).values(category_slug=slug))


def downgrade() -> None:
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint(FK, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_events_category_slug'))
        batch_op.drop_column('category_slug')
    op.drop_table('categories')
