"""Add analysis_runs table (Evidence-First Repository Intelligence).

Stores one row per evidence-first repository analysis: the domain `Analysis`
(Repository + Findings + Recommendations) produced by
app.cartographer.pipeline.analyze_repository_with_graph, plus the structural
`ProjectGraph` it was derived from, both as JSONB. See app/models/domain.py
for the Analysis contract, and app/cartographer/analysis_store.py for the
PostgresJsonbStore that reads and writes this table.

Revision: 006
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "006_analysis_runs"
down_revision = "005_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("repo_url", sa.Text, nullable=True),
        sa.Column("analysis", sa.dialects.postgresql.JSONB, nullable=False),
        # Nullable: the wiring diagram is derived data, kept so the Architecture
        # tab can reload a past run's graph, but an Analysis is valid without it.
        sa.Column("project_graph", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_analysis_runs_created_at",
        "analysis_runs",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_analysis_runs_created_at", table_name="analysis_runs")
    op.drop_table("analysis_runs")
