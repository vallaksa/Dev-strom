"""SQLAlchemy ORM models mapped to the Dev-Strom V3 database tables.

Each class mirrors a table created in migration 001_initial_schema.
Only tables needed by current V3 tickets are modelled here — add
the remaining tables (user_api_keys, web_chunks) when their tickets
are implemented.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.services.db import Base

# ── Anonymous user constant ────────────────────────────────────────────────────
# Used until auth is implemented (V3-4 through V3-9).
# Must match the UUID seeded into the `users` table.
ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


# ── users ──────────────────────────────────────────────────────────────────────
class User(Base):
    """Identity anchor. One row per authenticated user (or anonymous)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    google_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )

    runs: Mapped[list["Run"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ── runs ───────────────────────────────────────────────────────────────────────
class Run(Base):
    """One row per idea-generation call."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str | None] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, server_default="3", nullable=False)
    enable_multi_query: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False,
    )
    ideas: Mapped[dict] = mapped_column(JSONB, nullable=False)
    web_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )

    user: Mapped["User"] = relationship(back_populates="runs")
    expanded_ideas: Mapped[list["ExpandedIdea"]] = relationship(
        back_populates="run", cascade="all, delete-orphan",
    )


# ── expanded_ideas ─────────────────────────────────────────────────────────────
class ExpandedIdea(Base):
    """LLM expansion output for a specific idea position within a run."""

    __tablename__ = "expanded_ideas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    extended_plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )

    run: Mapped["Run"] = relationship(back_populates="expanded_ideas")


# ── cartograph_runs (F1: Project Cartographer) ──────────────────────────────────
class CartographRun(Base):
    """One row per Project Cartographer run: the parsed ProjectGraph and,
    once the LLM-analyzer agent has run, the derived ArchitectureReport.

    Both JSONB payloads are stored as plain dicts (pydantic `.model_dump()`
    output from app.cartographer.model.ProjectGraph / ArchitectureReport) -
    this ORM layer intentionally does not import those pydantic models, to
    keep the persistence layer decoupled from the contract's shape.
    """

    __tablename__ = "cartograph_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    project_graph: Mapped[dict] = mapped_column(JSONB, nullable=False)
    architecture_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )


# ── advisor_runs (F2: Improvement / Feature Advisor) ────────────────────────────
class AdvisorRun(Base):
    """One row per Improvement / Feature Advisor run: the prioritized
    AdvisorReport produced from a ProjectGraph (+ optional
    ArchitectureReport), plus provenance back to the cartograph run it was
    derived from (when it was loaded from one) and/or the repo it targeted.

    `cartograph_run_id` is a loose reference (no FK constraint) rather than
    a `ForeignKey("cartograph_runs.id")` on purpose: an advisor run can be
    produced from a fresh (unpersisted) cartograph pipeline run, in which
    case there is no cartograph_runs row to point at, so this column must
    stay nullable and unconstrained.

    `advisor_report` is stored as a plain dict (pydantic `.model_dump()`
    output from app.advisor.model.AdvisorReport) - this ORM layer
    intentionally does not import that pydantic model, to keep the
    persistence layer decoupled from the contract's shape (same pattern as
    CartographRun above).
    """

    __tablename__ = "advisor_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    cartograph_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    advisor_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )
