"""Add advisor_runs table (F2: Improvement / Feature Advisor).

Stores one row per advisor run: the prioritized AdvisorReport produced from
a ProjectGraph (+ optional ArchitectureReport), as JSONB, plus a loose
(unconstrained) reference back to the cartograph_runs row it was derived
from, when there was one. See app/advisor/model.py for the pydantic
contract this payload follows, and app/advisor/store.py for the
PostgresJsonbStore that reads and writes this table.

Revision: 004
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "004_advisor_runs"
down_revision = "003_cartograph_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advisor_runs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Intentionally no ForeignKey: a run can be produced from a fresh,
        # unpersisted cartograph pipeline run (see AdvisorRun docstring).
        sa.Column("cartograph_run_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("repo_url", sa.Text, nullable=True),
        sa.Column(
            "advisor_report",
            sa.dialects.postgresql.JSONB,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_advisor_runs_created_at",
        "advisor_runs",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_advisor_runs_cartograph_run_id",
        "advisor_runs",
        ["cartograph_run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_advisor_runs_cartograph_run_id", table_name="advisor_runs")
    op.drop_index("idx_advisor_runs_created_at", table_name="advisor_runs")
    op.drop_table("advisor_runs")
