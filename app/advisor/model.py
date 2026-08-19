"""Shared data contract for the Improvement / Feature Advisor (F2).

These pydantic models are THE contract between `app.advisor.advise`
(ProjectGraph [+ ArchitectureReport] -> AdvisorReport) and the rest of F2
(pipeline orchestration, persistence, API, UI). Mirrors the shape of
`app.cartographer.model` (F1): a permissive, LLM-authored report model with
a strict, hand-authored contract - do not duplicate or fork these
definitions elsewhere.
"""

from typing import Literal

from pydantic import BaseModel, Field

# ── Recommendation ───────────────────────────────────────────────────────────

RecommendationCategory = Literal[
    "feature",
    "refactor",
    "tech_debt",
    "risk",
    "test",
    "security",
    "performance",
    "docs",
]

ImpactLevel = Literal["high", "medium", "low"]
EffortLevel = Literal["high", "medium", "low"]


class Recommendation(BaseModel):
    """One actionable, prioritized recommendation grounded in the code graph.

    `affected_node_ids` should reference `id`s that appear in the
    ProjectGraph this recommendation was derived from, where evidence
    permits (not every recommendation - e.g. a cross-cutting risk - can be
    pinned to specific nodes).
    """

    id: str
    category: RecommendationCategory
    title: str
    rationale: str
    impact: ImpactLevel
    effort: EffortLevel
    affected_node_ids: list[str] = Field(default_factory=list)
    suggested_steps: list[str] = Field(default_factory=list)


# ── AdvisorReport ─────────────────────────────────────────────────────────────


class AdvisorReport(BaseModel):
    """LLM-authored, prioritized improvement roadmap for a codebase.

    Produced by `app.advisor.advise.advise()` from a ProjectGraph (and,
    when available, an ArchitectureReport) - the same "deterministic graph
    in, LLM report out" shape as F1's ArchitectureReport.
    """

    summary: str
    tech_stack: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)  # rec ids/titles
    strategic_bets: list[str] = Field(default_factory=list)  # rec ids/titles
