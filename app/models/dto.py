"""
DTO models — describe what crosses the HTTP boundary (request and response bodies).
These are shaped around the FastAPI contract, not the AI layer.
"""

from pydantic import BaseModel, Field, model_validator


class PriorIdeaRef(BaseModel):
    name: str
    problem_statement: str


# ── Requests ──────────────────────────────────────────────────────────────────

class IdeasRequest(BaseModel):
    # Either a natural-language `intent` (the new NL-first input, plan §2) or a
    # structured `tech_stack` — at least one is required. When only `intent` is
    # given, the graph infers the stack/domain/complexity from it.
    intent: str | None = Field(default=None, description="Natural-language description of what to build")
    tech_stack: str | None = None
    domain: str | None = None
    level: str | None = None
    enable_multi_query: bool = Field(
        default=False,
        description="Deprecated — no longer affects web context (Sonar + Tavily fallback). Stored on runs for history only.",
    )
    count: int = Field(default=2, ge=1, le=5)
    refinement_context: str | None = Field(
        default=None, description="Optional extra context when generating more ideas"
    )
    prior_ideas: list[PriorIdeaRef] | None = Field(
        default=None,
        description="Ideas already shown in the UI; generation must avoid duplicates",
    )

    @model_validator(mode="after")
    def _requires_intent_or_tech_stack(self) -> "IdeasRequest":
        if not (self.intent and self.intent.strip()) and not (self.tech_stack and self.tech_stack.strip()):
            raise ValueError("Provide at least one of 'intent' or 'tech_stack'.")
        return self

    @property
    def resolved_tech_stack(self) -> str:
        """Stack string used for search/storage; falls back to intent text."""
        if self.tech_stack and self.tech_stack.strip():
            return self.tech_stack.strip()
        assert self.intent is not None
        return self.intent.strip()


class ExpandRequest(BaseModel):
    run_id: str = Field(..., description="Public run slug from POST /ideas")
    pid: int = Field(..., ge=1, description="ID of the idea to expand (1-based from that run)")


class ExportRequest(BaseModel):
    run_id: str = Field(..., description="Public run slug from POST /ideas")
    pid: int = Field(..., ge=1, description="ID of the expanded idea to export (must have been expanded first)")


# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────
# The response is the domain `Analysis` (app.models.domain) dumped to dict,
# plus two top-level extras the UI's Architecture tab consumes: `graph` (the
# structural ProjectGraph) and `mermaid` (reserved; null today). Typed as
# `dict` here — the API dumps the real pydantic models before returning.

class AnalyzeRequest(BaseModel):
    repo_url: str | None = Field(default=None, description="Git URL of the repo to analyze")
    path: str | None = Field(default=None, description="Local filesystem path to the repo to analyze")

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "AnalyzeRequest":
        has_repo = bool(self.repo_url and self.repo_url.strip())
        has_path = bool(self.path and self.path.strip())
        if has_repo == has_path:  # neither or both provided
            raise ValueError("Provide exactly one of 'repo_url' or 'path'.")
        return self


class AnalyzeResponse(BaseModel):
    run_id: str
    id: str
    status: str
    summary: str
    repository: dict
    findings: list[dict]
    recommendations: list[dict]
    graph: dict | None = None
    mermaid: str | None = None


class AnalysisSummary(BaseModel):
    """One lightweight History-list row (not the full Analysis)."""

    run_id: str
    repo_url: str | None = None
    language: str | None = None
    status: str | None = None
    finding_count: int = 0
    recommendation_count: int = 0
    created_at: str


class AnalysisListResponse(BaseModel):
    analyses: list[AnalysisSummary]
    limit: int
    offset: int


# ── Async Jobs (F4) ───────────────────────────────────────────────────────────
# Documents the `?async=true` response shape for POST /analyze and the
# GET /jobs/{job_id} response shape.

class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str = Field(default="pending", description="Always 'pending' immediately after scheduling")


class JobResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    params: dict
    result: dict | None = None
    error: str | None = None
    created_at: str
    updated_at: str
