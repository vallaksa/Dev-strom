"""Add unique public slug to run tables.

UUID stays the primary key. API/UI `run_id` is the slug (owner-repo or
intent text), unique per table. Existing rows are backfilled from
repo_url / tech_stack / root_path.

Revision: 007
"""

import sqlalchemy as sa
from alembic import op

from app.services.slugs import slug_from_repo, slugify, unique_slug

revision = "007_run_slugs"
down_revision = "006_analysis_runs"
branch_labels = None
depends_on = None

_TABLES = (
    "runs",
    "analysis_runs",
    "cartograph_runs",
    "advisor_runs",
)


def _slug_base(value: str | None, *, from_repo: bool) -> str:
    if not from_repo:
        return slugify(value)
    if value and ("://" in value or value.startswith("git@")):
        return slug_from_repo(value)
    return slug_from_repo(None, value)


def _backfill(conn, table: str, expr: str, *, from_repo: bool) -> None:
    rows = conn.execute(
        sa.text(f"SELECT id, {expr} AS base FROM {table} ORDER BY created_at")
    ).fetchall()
    taken: set[str] = set()
    for row in rows:
        slug = unique_slug(_slug_base(row.base, from_repo=from_repo), taken)
        taken.add(slug)
        conn.execute(
            sa.text(f"UPDATE {table} SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": row.id},
        )


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("slug", sa.Text(), nullable=True))

    conn = op.get_bind()
    _backfill(conn, "runs", "tech_stack", from_repo=False)
    _backfill(conn, "analysis_runs", "repo_url", from_repo=True)
    _backfill(conn, "cartograph_runs", "COALESCE(repo_url, root_path)", from_repo=True)
    _backfill(conn, "advisor_runs", "repo_url", from_repo=True)

    for table in _TABLES:
        op.alter_column(table, "slug", existing_type=sa.Text(), nullable=False)
        op.create_index(f"uq_{table}_slug", table, ["slug"], unique=True)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"uq_{table}_slug", table_name=table)
        op.drop_column(table, "slug")
