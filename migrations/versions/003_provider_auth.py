"""Provider-agnostic auth identity + user-scoped analysis runs.

- users: replace `google_id` with (`auth_provider`, `provider_user_id`),
  unique together. The anonymous seed row becomes ("system", "anonymous");
  any real pre-existing rows are assumed Google.
- analysis_runs: add `user_id` (FK users, NOT NULL, defaults to the
  anonymous user so existing rows stay valid).

Revision: 003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "003_provider_auth"
down_revision = "002_seed_anonymous_user"
branch_labels = None
depends_on = None

_ANON_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # ── users: google_id → (auth_provider, provider_user_id) ──────────────
    op.add_column("users", sa.Column("auth_provider", sa.Text, nullable=True))
    op.add_column("users", sa.Column("provider_user_id", sa.Text, nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE users SET
              auth_provider = CASE WHEN id = :anon THEN 'system' ELSE 'google' END,
              provider_user_id = CASE WHEN id = :anon THEN 'anonymous' ELSE google_id END
            """
        ).bindparams(anon=_ANON_ID)
    )

    op.alter_column("users", "auth_provider", nullable=False)
    op.alter_column("users", "provider_user_id", nullable=False)
    op.drop_constraint("users_google_id_key", "users", type_="unique")
    op.drop_column("users", "google_id")
    op.create_unique_constraint(
        "uq_users_provider_identity", "users", ["auth_provider", "provider_user_id"]
    )

    # ── analysis_runs: user_id ───────────────────────────────────────────
    op.add_column(
        "analysis_runs",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            server_default=_ANON_ID,
        ),
    )
    op.create_index("idx_analysis_runs_user_id", "analysis_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_analysis_runs_user_id", "analysis_runs")
    op.drop_column("analysis_runs", "user_id")

    op.add_column("users", sa.Column("google_id", sa.Text, nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users SET google_id =
              CASE WHEN provider_user_id = 'anonymous' THEN 'anonymous'
                   ELSE provider_user_id END
            """
        )
    )
    op.alter_column("users", "google_id", nullable=False)
    op.create_unique_constraint("users_google_id_key", "users", ["google_id"])
    op.drop_constraint("uq_users_provider_identity", "users", type_="unique")
    op.drop_column("users", "provider_user_id")
    op.drop_column("users", "auth_provider")
