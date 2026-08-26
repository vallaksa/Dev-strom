"""
Domain models — the core objects Dev-Strom reasons about.

These are shaped around the *product's* domain (per the Product Evolution
Plan §12), not around individual LangGraph nodes or the HTTP boundary:

    Analysis
       ├── Repository        (metadata, deterministically ingested)
       ├── Finding[]         (evidence-backed observations)
       └── Recommendation[]  (actionable improvements derived from findings)

The idea-generation experience keeps its own domain objects (`ProjectIdea`
/ `Idea`) so the platform can grow the "Understand / Improve" side without
forcing everything through a generic "run".

NOTE ON NAMING: `app.advisor.model.Recommendation` is a *separate*,
LLM-report-shaped contract used by the F2 Advisor pipeline. The
`Recommendation` here is the platform-level domain object described in the
plan (id / finding_id / type / impact / effort / priority) and is
deliberately distinct — do not conflate the two.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Idea generation (existing "CREATE" experience) ────────────────────────────

class ProjectIdea(BaseModel):
    name: str = Field(..., description="Project name")
    problem_statement: str = Field(..., description="1–2 sentences describing the problem")
    why_it_fits: list[str] = Field(..., description="Short bullets per tech in the stack")
    real_world_value: str = Field(..., description="One sentence on real-world value")
    implementation_plan: list[str] = Field(..., description="3–5 high-level implementation steps")
    # ── Engineering-context enrichment (optional; graceful degradation) ────────
    # Added so idea cards can "teach engineering while generating ideas" (plan
    # §3). Optional with defaults so older persisted ideas and the strict
    # required-field validation both keep working.
    business_value: str = Field(default="", description="Business impact; UI falls back to real_world_value")
    engineering_challenges: list[str] = Field(
        default_factory=list, description="The hard engineering problems this project surfaces"
    )
    architectural_intent: str = Field(
        default="", description="Why the suggested architecture is shaped this way"
    )
    tradeoffs: list[str] = Field(
        default_factory=list, description="Key design tradeoffs the builder will weigh"
    )


class IdeasResponse(BaseModel):
    ideas: list[ProjectIdea] = Field(..., min_length=1, max_length=5)


class ExpandedIdea(BaseModel):
    idea: ProjectIdea
    extended_plan: list[str] = Field(..., description="Deeper implementation steps or next steps")


class Idea(BaseModel):
    """A first-class, persisted project idea (plan §12).

    Richer than `ProjectIdea` (which mirrors the LLM's raw structured output):
    it carries the identity/provenance the product needs to store, list, and
    reference ideas over time.
    """

    id: str = Field(..., description="Stable idea id")
    run_id: str | None = Field(default=None, description="Owning generation run, if any")
    title: str
    description: str = Field(..., description="What this project is, in 1–2 sentences")
    business_value: str = Field(default="", description="Why it matters in the real world")
    engineering_challenges: list[str] = Field(default_factory=list)
    architecture: str = Field(default="", description="Suggested architecture sketch / notes")


# ── Repository ingestion ("UNDERSTAND") ──────────────────────────────────────

class Dependency(BaseModel):
    """One external dependency discovered deterministically from a manifest.

    `ecosystem` is the manifest/package-manager it came from (e.g. "pypi",
    "npm", "go", "maven") so the same repo's Python and JS deps stay
    distinguishable without an LLM.
    """

    name: str
    ecosystem: str = Field(..., description="pypi | npm | go | maven | ...")
    source: str = Field(..., description="Manifest filename the dep was read from")
    version: str | None = None


class Repository(BaseModel):
    """A deterministically-ingested view of a codebase (plan §12 / §17).

    Everything here is produced by ordinary software (clone + parse), never
    an LLM: this is the reliable structural/metadata layer that AI reasoning
    is layered on top of. `language` is the single primary language;
    `languages` is the full set detected.
    """

    id: str = Field(..., description="Stable repository id (deterministic for a given url+commit)")
    url: str | None = Field(default=None, description="Source git URL, if cloned from one")
    root_path: str = Field(..., description="Local filesystem root the repo was ingested from")
    commit_sha: str | None = Field(default=None, description="Resolved HEAD commit, if available")
    language: str | None = Field(default=None, description="Primary language (most code files)")
    languages: list[str] = Field(default_factory=list, description="All code languages detected")
    dependencies: list[Dependency] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list, description="Detected entrypoint node ids")
    file_count: int = 0
    loc: int = Field(default=0, description="Total lines of code walked")
    created_at: datetime = Field(default_factory=_utcnow)


# ── Findings + Recommendations (Evidence-First "IMPROVE") ─────────────────────

FindingCategory = Literal[
    "architecture",
    "design",
    "scalability",
    "reliability",
    "security",
    "performance",
    "maintainability",
    "testing",
    "product",
]

Severity = Literal["critical", "high", "medium", "low", "info"]

RecommendationType = Literal[
    "product",
    "engineering",
    "scalability",
    "reliability",
    "security",
    "developer_experience",
]

ImpactLevel = Literal["high", "medium", "low"]
EffortLevel = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    """A concrete pointer back into the repository that grounds a Finding.

    This is the heart of the "Evidence-First" principle (plan §13): every
    important conclusion should point at real code — a file, a line/range, a
    symbol — plus a short explanation of what that code shows. All locators
    are optional individually (some evidence is a file-level observation with
    no single line), but a finding with no evidence at all is a smell the
    analysis layer is expected to avoid.
    """

    file: str | None = Field(default=None, description="Repo-relative path")
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    symbol: str | None = Field(default=None, description="Class / function / module symbol")
    snippet: str | None = Field(default=None, description="Short quoted code excerpt")
    explanation: str = Field(..., description="What this evidence shows and why it matters")


class Finding(BaseModel):
    """One evidence-backed observation about a repository (plan §12 / §13).

    `confidence` is a 0–1 score (not a level) so the UI and any downstream
    ranking can reason about it numerically; low-confidence findings should
    be surfaced as such rather than dropped silently.
    """

    id: str
    repository_id: str
    category: FindingCategory
    title: str
    description: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: Severity = "info"


class Recommendation(BaseModel):
    """An actionable improvement derived from a Finding (plan §12 / §6.4).

    `finding_id` links back to the evidence-backed finding that motivates it,
    keeping recommendations traceable rather than free-floating suggestions.
    `priority` is a 1-based rank (1 = act on first) so the "Improvements" tab
    can render an ordered, HIGH→MEDIUM list directly.
    """

    id: str
    finding_id: str | None = Field(default=None, description="Source finding, if any")
    type: RecommendationType
    title: str
    description: str
    impact: ImpactLevel = "medium"
    effort: EffortLevel = "medium"
    priority: int = Field(default=1, ge=1, description="1-based rank; lower acts first")


class Analysis(BaseModel):
    """The top-level result of understanding + improving a repository (plan §12).

    Aggregates the deterministically-ingested `Repository` with the
    evidence-backed `Finding`s and the `Recommendation`s derived from them.
    `summary` is the human-readable "System Overview". `status` lets callers
    represent an in-flight/failed analysis without a separate job object.
    """

    id: str
    repository: Repository
    summary: str = Field(default="", description="System overview / what this system does")
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    mermaid: str | None = Field(
        default=None,
        description="Optional component-level architecture diagram (Mermaid flowchart source)",
    )
    status: Literal["pending", "complete", "failed"] = "complete"
    created_at: datetime = Field(default_factory=_utcnow)
