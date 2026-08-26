"""Unit tests for the new platform domain models (app.models.domain):
Repository / Dependency / Evidence / Finding / Recommendation / Analysis.

Pure/hermetic: just pydantic construction and validation, no I/O.
"""

import pytest
from pydantic import ValidationError

from app.models.domain import (
    Analysis,
    Dependency,
    Evidence,
    Finding,
    Recommendation,
    Repository,
)


def _repo(**overrides) -> Repository:
    base = dict(id="repo-1", root_path="/tmp/repo")
    base.update(overrides)
    return Repository(**base)


def test_repository_defaults_and_created_at():
    repo = _repo(url="https://example.com/x.git", language="python", languages=["python", "sql"])
    assert repo.commit_sha is None
    assert repo.dependencies == []
    assert repo.file_count == 0
    # created_at is populated automatically and timezone-aware
    assert repo.created_at.tzinfo is not None


def test_dependency_requires_ecosystem_and_source():
    dep = Dependency(name="fastapi", ecosystem="pypi", source="requirements.txt")
    assert dep.version is None
    with pytest.raises(ValidationError):
        Dependency(name="fastapi")  # missing ecosystem + source


def test_evidence_requires_explanation():
    ev = Evidence(file="app/x.py", symbol="X.run", explanation="calls three services in a row")
    assert ev.line_start is None
    with pytest.raises(ValidationError):
        Evidence(file="app/x.py")  # explanation is required


def test_evidence_line_numbers_must_be_positive():
    with pytest.raises(ValidationError):
        Evidence(explanation="x", line_start=0)


def test_finding_confidence_bounds_and_enums():
    f = Finding(
        id="finding-1",
        repository_id="repo-1",
        category="scalability",
        title="Synchronous bottleneck",
        description="Sequential downstream calls.",
        evidence=[Evidence(explanation="three sequential awaits")],
        confidence=0.8,
        severity="high",
    )
    assert f.severity == "high"
    with pytest.raises(ValidationError):
        Finding(
            id="f", repository_id="r", category="scalability",
            title="t", description="d", confidence=1.5,  # out of [0,1]
        )
    with pytest.raises(ValidationError):
        Finding(
            id="f", repository_id="r", category="not-a-category",  # bad enum
            title="t", description="d",
        )


def test_finding_defaults():
    f = Finding(id="f", repository_id="r", category="design", title="t", description="d")
    assert f.evidence == []
    assert f.confidence == 0.5
    assert f.severity == "info"


def test_recommendation_priority_and_links():
    rec = Recommendation(
        id="rec-1",
        finding_id="finding-1",
        type="scalability",
        title="Parallelize downstream calls",
        description="Use asyncio.gather where ordering is not required.",
        impact="high",
        effort="medium",
        priority=1,
    )
    assert rec.finding_id == "finding-1"
    with pytest.raises(ValidationError):
        Recommendation(id="r", type="engineering", title="t", description="d", priority=0)
    with pytest.raises(ValidationError):
        Recommendation(id="r", type="bogus", title="t", description="d")


def test_recommendation_finding_id_optional():
    rec = Recommendation(id="r", type="product", title="t", description="d")
    assert rec.finding_id is None
    assert rec.priority == 1


def test_analysis_aggregates_repository_findings_recommendations():
    repo = _repo()
    analysis = Analysis(
        id="a1",
        repository=repo,
        summary="A small service.",
        findings=[Finding(id="finding-1", repository_id=repo.id, category="testing",
                          title="No tests", description="…")],
        recommendations=[Recommendation(id="rec-1", finding_id="finding-1", type="engineering",
                                        title="Add tests", description="…")],
    )
    assert analysis.status == "complete"
    assert analysis.mermaid is None  # optional architecture diagram, absent by default
    assert analysis.repository.id == "repo-1"
    assert analysis.findings[0].repository_id == repo.id
    # round-trips through JSON mode cleanly (datetime -> isoformat)
    dumped = analysis.model_dump(mode="json")
    assert dumped["repository"]["id"] == "repo-1"
    assert dumped["findings"][0]["category"] == "testing"


def test_idea_platform_model_requires_identity_and_title():
    from app.models.domain import Idea

    idea = Idea(
        id="idea-1",
        title="Event Bus Lab",
        description="Learn distributed messaging.",
        engineering_challenges=["Ordering", "At-least-once delivery"],
    )
    assert idea.run_id is None
    assert idea.architecture == ""
    with pytest.raises(ValidationError):
        Idea(title="missing id", description="d")
