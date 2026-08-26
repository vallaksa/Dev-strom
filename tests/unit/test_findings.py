"""Unit tests for app.cartographer.findings: the evidence-first structured
analysis (ProjectGraph + Repository -> Analysis).

Hermetic/mockable in the same spirit as test_analyze.py: `parse_analysis`
never touches the network, and `analyze_findings` is exercised with
`_invoke_with_fallback` monkeypatched so no real LLM/model call happens.
"""

import json

import app.cartographer.findings as findings
from app.models.domain import Analysis, Repository


def _repo() -> Repository:
    return Repository(id="repo-xyz", root_path="/tmp/repo", language="python")


def _valid_analysis_dict() -> dict:
    return {
        "summary": "A FastAPI service that maps and analyzes repositories.",
        "findings": [
            {
                "category": "scalability",
                "title": "Synchronous analysis blocks the request",
                "description": "Cartograph runs inline on the HTTP request.",
                "confidence": 0.75,
                "severity": "high",
                "evidence": [
                    {
                        "file": "app/api.py",
                        "symbol": "post_cartograph",
                        "explanation": "clone+parse+LLM all run before the response returns",
                    }
                ],
            },
            {
                "category": "testing",
                "title": "No integration tests around the pipeline",
                "description": "…",
                "confidence": 0.4,
                "severity": "medium",
                "evidence": [{"explanation": "no tests/integration entries touch the pipeline"}],
            },
        ],
        "recommendations": [
            {
                "finding_ref": 0,
                "type": "scalability",
                "title": "Move analysis to a background job",
                "description": "Return a job id and process asynchronously.",
                "impact": "high",
                "effort": "medium",
                "priority": 1,
            },
            {
                "type": "developer_experience",
                "title": "Add pipeline integration tests",
                "description": "…",
                "impact": "medium",
                "effort": "low",
                "priority": 2,
            },
        ],
    }


# ── parse_analysis ────────────────────────────────────────────────────────────

def test_parse_analysis_valid_grounds_findings_in_repository():
    repo = _repo()
    analysis = findings.parse_analysis(json.dumps(_valid_analysis_dict()), repo)

    assert isinstance(analysis, Analysis)
    assert analysis.status == "complete"
    assert analysis.repository.id == "repo-xyz"
    assert analysis.summary.startswith("A FastAPI service")

    assert len(analysis.findings) == 2
    # repository_id is set from the passed Repository, never from the model
    assert all(f.repository_id == "repo-xyz" for f in analysis.findings)
    assert analysis.findings[0].evidence[0].file == "app/api.py"
    assert analysis.findings[0].confidence == 0.75


def test_parse_analysis_resolves_finding_ref_to_finding_id():
    analysis = findings.parse_analysis(json.dumps(_valid_analysis_dict()), _repo())
    recs = analysis.recommendations
    assert len(recs) == 2
    # finding_ref=0 -> first finding's id
    assert recs[0].finding_id == analysis.findings[0].id
    # no finding_ref -> cross-cutting recommendation
    assert recs[1].finding_id is None


def test_parse_analysis_strips_markdown_fences():
    raw = "```json\n" + json.dumps(_valid_analysis_dict()) + "\n```"
    analysis = findings.parse_analysis(raw, _repo())
    assert analysis.status == "complete"
    assert len(analysis.findings) == 2


def test_parse_analysis_coerces_out_of_range_enums():
    data = {
        "summary": "s",
        "findings": [
            {"category": "made-up", "title": "T", "description": "d", "severity": "extreme",
             "confidence": 9.0, "evidence": [{"explanation": "x"}]}
        ],
        "recommendations": [
            {"type": "nonsense", "title": "R", "description": "d", "impact": "huge", "effort": "tiny"}
        ],
    }
    analysis = findings.parse_analysis(json.dumps(data), _repo())
    f = analysis.findings[0]
    assert f.category == "architecture"   # default
    assert f.severity == "info"           # default
    assert f.confidence == 1.0            # clamped into [0,1]
    r = analysis.recommendations[0]
    assert r.type == "engineering"        # default
    assert r.impact == "medium" and r.effort == "medium"
    assert r.priority == 1                # defaulted to its 1-based position


def test_parse_analysis_drops_evidence_without_explanation():
    data = {
        "summary": "s",
        "findings": [
            {"category": "design", "title": "T", "description": "d",
             "evidence": [{"file": "app/x.py"}, {"explanation": "real one"}]}
        ],
        "recommendations": [],
    }
    analysis = findings.parse_analysis(json.dumps(data), _repo())
    ev = analysis.findings[0].evidence
    assert len(ev) == 1
    assert ev[0].explanation == "real one"


def test_parse_analysis_skips_findings_without_title():
    data = {"summary": "s", "findings": [{"category": "design", "description": "no title"}],
            "recommendations": []}
    analysis = findings.parse_analysis(json.dumps(data), _repo())
    assert analysis.findings == []


def test_parse_analysis_garbage_returns_failed_minimal_analysis():
    analysis = findings.parse_analysis("not json at all {{{", _repo())
    assert analysis.status == "failed"
    assert analysis.findings == []
    assert analysis.recommendations == []
    assert "could not be parsed" in analysis.summary
    assert analysis.repository.id == "repo-xyz"


def test_parse_analysis_non_object_json_is_failed():
    analysis = findings.parse_analysis(json.dumps(["a", "list"]), _repo())
    assert analysis.status == "failed"


# ── analyze_findings (mocked agent) ──────────────────────────────────────────

class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


def test_analyze_findings_happy_path_uses_mocked_agent(monkeypatch):
    raw = json.dumps(_valid_analysis_dict())

    def fake_invoke(get_agent, messages):
        assert callable(get_agent)
        assert messages and messages[0]["role"] == "user"
        return {"messages": [_FakeMessage(raw)]}

    monkeypatch.setattr(findings, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [{"id": "n1", "type": "module", "label": "app.api"}], "edges": []}
    analysis = findings.analyze_findings(graph, _repo())

    assert analysis.status == "complete"
    assert len(analysis.findings) == 2
    assert analysis.recommendations[0].finding_id == analysis.findings[0].id


def test_analyze_findings_agent_failure_returns_failed_analysis(monkeypatch):
    def fake_invoke(get_agent, messages):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(findings, "_invoke_with_fallback", fake_invoke)

    analysis = findings.analyze_findings({"nodes": [], "edges": []}, _repo())
    assert analysis.status == "failed"
    assert "Analysis failed" in analysis.summary
    assert analysis.repository.id == "repo-xyz"
