"""clubs and follows

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-05

Club pages (/club/<slug>) and follows: organizers.slug (backfilled from the name), the follows table,
and users.follow_updates ("Updates from clubs I follow", on by default).
"""
import re

from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:60] or "club"


def upgrade() -> None:
    op.create_table(
        'follows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.String(length=36), nullable=False),
        sa.Column('organizer_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organizer_id'], ['organizers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'organizer_id'),
    )
    op.create_index('ix_follows_organizer', 'follows', ['organizer_id'], unique=False)
    # Plain ADD COLUMN (no table copy) works the same on SQLite and PostgreSQL.
    op.add_column('organizers', sa.Column('slug', sa.String(length=80), nullable=True))
    op.add_column('users', sa.Column('follow_updates', sa.Boolean(), server_default=sa.true(), nullable=False))

    conn = op.get_bind()
    orgs = sa.table("organizers", sa.column("id", sa.String), sa.column("org_name", sa.String), sa.column("slug", sa.String))
    taken: set[str] = set()
    for row in conn.execute(sa.select(orgs.c.id, orgs.c.org_name).order_by(orgs.c.id)).all():
        base = slug = _slugify(row.org_name)
        n = 1
        while slug in taken:
            n += 1
            slug = f"{base}-{n}"
        taken.add(slug)
        conn.execute(orgs.update().where(orgs.c.id == row.id).values(slug=slug))
    op.create_index(op.f('ix_organizers_slug'), 'organizers', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_organizers_slug'), table_name='organizers')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('follow_updates')
    with op.batch_alter_table('organizers', schema=None) as batch_op:
        batch_op.drop_column('slug')
    op.drop_index('ix_follows_organizer', table_name='follows')
    op.drop_table('follows')
