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


# ── analysis_runs (Evidence-First Repository Intelligence) ──────────────────────
class AnalysisRun(Base):
    """One row per evidence-first repository analysis (app.cartographer.pipeline
    .analyze_repository_with_graph): the domain `Analysis` (Repository +
    Findings + Recommendations) plus the structural `ProjectGraph` it was
    derived from, both as JSONB.

    `analysis` is `app.models.domain.Analysis.model_dump()`; `project_graph`
    is `app.cartographer.model.ProjectGraph.model_dump()` (nullable — kept so
    the Architecture tab can reload a past run's wiring diagram). As with
    CartographRun / AdvisorRun, this ORM layer intentionally does not import
    those pydantic models, keeping persistence decoupled from their shape.
    """

    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis: Mapped[dict] = mapped_column(JSONB, nullable=False)
    project_graph: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )


# ── jobs (F4-surface: in-process background job runner) ─────────────────────────
class Job(Base):
    """One row per background job (e.g. an async /cartograph or /advise run).

    `params` captures the inputs the job was started with; `result` is set
    once the job finishes successfully (must be JSON-serializable); `error`
    is set (as a plain string, via `str(exc)`) if the job's function raised.
    `status` is one of app.services.jobs.JobStatus's values, stored as plain
    text rather than a Postgres enum to keep migrations simple.

    `updated_at` has a server_default for row creation, but Postgres does not
    auto-update it on UPDATE without a trigger - app.services.jobs.run_job
    is responsible for setting it explicitly on every status transition.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"),
    )
