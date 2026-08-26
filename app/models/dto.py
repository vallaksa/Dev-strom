"""
DTO models — describe what crosses the HTTP boundary (request and response bodies).
These are shaped around the FastAPI contract, not the AI layer.
"""

from pydantic import BaseModel, Field, model_validator


# ── Requests ──────────────────────────────────────────────────────────────────

class IdeasRequest(BaseModel):
    # Either a natural-language `intent` (the new NL-first input, plan §2) or a
    # structured `tech_stack` — at least one is required. When only `intent` is
    # given, the graph infers the stack/domain/complexity from it.
    intent: str | None = Field(default=None, description="Natural-language description of what to build")
    tech_stack: str | None = None
    domain: str | None = None
    level: str | None = None
    enable_multi_query: bool = False
    count: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def _requires_intent_or_tech_stack(self) -> "IdeasRequest":
        if not (self.intent and self.intent.strip()) and not (self.tech_stack and self.tech_stack.strip()):
            raise ValueError("Provide at least one of 'intent' or 'tech_stack'.")
        return self


class ExpandRequest(BaseModel):
    run_id: str = Field(..., description="Run ID from POST /ideas response")
    pid: int = Field(..., ge=1, description="ID of the idea to expand (1-based from that run)")


class ExportRequest(BaseModel):
    run_id: str = Field(..., description="Run ID from POST /ideas response")
    pid: int = Field(..., ge=1, description="ID of the expanded idea to export (must have been expanded first)")


# ── Project Cartographer (F1) ────────────────────────────────────────────────
# NOTE: project_graph / architecture_report below are typed as plain `dict`
# rather than the real `ProjectGraph` / `ArchitectureReport` pydantic models
# (app.cartographer.model, owned by feat/f1-core and not yet present in this
# worktree). The API layer dumps those models to dict before returning, so a
# generic dict field here is deliberate — it decouples this DTO from a
# contract module that doesn't exist yet, and still documents the response
# shape. Tighten to the real types once feat/f1-core lands.

class CartographRequest(BaseModel):
    repo_url: str | None = Field(default=None, description="Git URL of the repo to map")
    path: str | None = Field(default=None, description="Local filesystem path to the repo to map")

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "CartographRequest":
        has_repo = bool(self.repo_url and self.repo_url.strip())
        has_path = bool(self.path and self.path.strip())
        if has_repo == has_path:  # neither or both provided
            raise ValueError("Provide exactly one of 'repo_url' or 'path'.")
        return self


class CartographResponse(BaseModel):
    run_id: str
    project_graph: dict
    architecture_report: dict


# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────
# The response is the domain `Analysis` (app.models.domain) dumped to dict,
# plus two top-level extras the UI's Architecture tab consumes: `graph` (the
# structural ProjectGraph, same shape /cartograph returns as project_graph)
# and `mermaid` (reserved; null today). Typed as `dict` here for the same
# reason CartographResponse's fields are — the API dumps the real pydantic
# models before returning, keeping this DTO decoupled from their shape.

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


# ── Improvement / Feature Advisor (F2) ───────────────────────────────────────
# advisor_report below is typed as plain `dict` for the same reason
# CartographResponse's fields are: the API layer dumps the real
# `app.advisor.model.AdvisorReport` pydantic model to dict before returning,
# so this DTO stays decoupled from that contract module's exact shape.

class AdviseRequest(BaseModel):
    repo_url: str | None = Field(default=None, description="Git URL of the repo to map and advise on")
    path: str | None = Field(default=None, description="Local filesystem path to the repo to map and advise on")
    run_id: str | None = Field(default=None, description="An existing cartograph run ID to advise against")

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "AdviseRequest":
        provided = [
            bool(self.repo_url and self.repo_url.strip()),
            bool(self.path and self.path.strip()),
            bool(self.run_id and self.run_id.strip()),
        ]
        if sum(provided) != 1:
            raise ValueError("Provide exactly one of 'repo_url', 'path', or 'run_id'.")
        return self


class AdviseResponse(BaseModel):
    run_id: str
    advisor_report: dict


# ── Async Jobs (F4) ───────────────────────────────────────────────────────────
# Documents the `?async=true` response shape for POST /cartograph and
# POST /advise, and the GET /jobs/{job_id} response shape. Like
# CartographResponse/AdviseResponse above, these aren't wired up as FastAPI
# response_model today - just documentation of the contract.

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
