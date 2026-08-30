"""Add jobs table (F4-surface: in-process background job runner).

Stores one row per background job (e.g. an async POST /analyze run) so a
client can poll GET /jobs/{job_id} for status/result instead of blocking
the original HTTP request on the full pipeline. See app/services/jobs.py
for the create_job/get_job/run_job primitives that read and write this table,
and app/services/models.py's `Job` ORM class for the column contract.

Revision: 005
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "005_jobs"
down_revision = "004_advisor_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "params",
            sa.dialects.postgresql.JSONB,
            nullable=False,
        ),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB,
            nullable=True,
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_jobs_created_at",
        "jobs",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_table("jobs")
