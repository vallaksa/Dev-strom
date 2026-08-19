"""Add cartograph_runs table (F1: Project Cartographer).

Stores one row per cartographer run: the parsed ProjectGraph and, once the
LLM-analyzer agent has produced one, the ArchitectureReport - both as JSONB.
See app/cartographer/model.py for the pydantic contract these payloads
follow, and app/cartographer/store.py for the PostgresJsonbStore that reads
and writes this table.

Revision: 003
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "003_cartograph_runs"
down_revision = "002_seed_anonymous_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cartograph_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("repo_url", sa.Text, nullable=True),
        sa.Column("root_path", sa.Text, nullable=False),
        sa.Column(
            "project_graph",
            sa.dialects.postgresql.JSONB,
            nullable=False,
        ),
        sa.Column(
            "architecture_report",
            sa.dialects.postgresql.JSONB,
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_cartograph_runs_created_at",
        "cartograph_runs",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_cartograph_runs_created_at", table_name="cartograph_runs")
    op.drop_table("cartograph_runs")
