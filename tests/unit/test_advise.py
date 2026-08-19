"""Unit tests for app/advisor/advise.py's JSON parsing/validation, the
mockable agent-invocation path, and the graph-summary builder's size cap.

Unlike tests/unit/test_analyze.py (written before F1 had merged into that
worktree), F1 is already merged here, so app.cartographer.model /
app.advisor.model are imported directly - no sys.modules stub needed.
"""

import json

import app.advisor.advise as advise_mod


def _valid_report_dict() -> dict:
    return {
        "summary": "A FastAPI + Streamlit app with a thin service layer and no test coverage on the API routes.",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        "recommendations": [
            {
                "id": "rec-1",
                "category": "test",
                "title": "Add integration tests for POST /ideas",
                "rationale": "app/api.py has no direct test coverage evidenced in the graph.",
                "impact": "high",
                "effort": "low",
                "affected_node_ids": ["n1"],
                "suggested_steps": ["Add a TestClient-based test", "Monkeypatch the graph app"],
            },
            {
                "id": "rec-2",
                "category": "refactor",
                "title": "Extract shared JSON-parsing helpers",
                "rationale": "Fence-stripping logic is duplicated across modules.",
                "impact": "medium",
                "effort": "medium",
                "affected_node_ids": ["n2"],
                "suggested_steps": ["Move helpers to a shared module"],
            },
        ],
        "quick_wins": ["rec-1"],
        "strategic_bets": [],
    }


# ── parse_advisor_report ────────────────────────────────────────────────────


def test_parse_advisor_report_valid_json():
    raw = json.dumps(_valid_report_dict())
    report = advise_mod.parse_advisor_report(raw)
    assert report.summary.startswith("A FastAPI + Streamlit app")
    assert report.tech_stack == ["Python", "FastAPI", "PostgreSQL"]
    assert len(report.recommendations) == 2
    assert report.recommendations[0].id == "rec-1"
    assert report.recommendations[0].category == "test"
    assert report.recommendations[0].impact == "high"
    assert report.recommendations[0].effort == "low"
    assert report.quick_wins == ["rec-1"]


def test_parse_advisor_report_strips_markdown_fences():
    raw = "```json\n" + json.dumps(_valid_report_dict()) + "\n```"
    report = advise_mod.parse_advisor_report(raw)
    assert report.tech_stack == ["Python", "FastAPI", "PostgreSQL"]


def test_parse_advisor_report_garbage_returns_minimal_report():
    report = advise_mod.parse_advisor_report("not json at all {{{")
    assert report.summary == ""
    assert report.tech_stack == []
    assert len(report.recommendations) == 1
    assert report.recommendations[0].category == "risk"
    assert "could not be parsed" in report.recommendations[0].rationale
    assert report.quick_wins == []
    assert report.strategic_bets == []


def test_parse_advisor_report_schema_mismatch_returns_minimal_report():
    # Valid JSON, but a recommendation with an invalid category enum value.
    bad = _valid_report_dict()
    bad["recommendations"][0]["category"] = "not-a-real-category"
    report = advise_mod.parse_advisor_report(json.dumps(bad))
    assert report.summary == ""
    assert len(report.recommendations) == 1
    assert report.recommendations[0].id == "rec-error"


# ── summarize_graph ─────────────────────────────────────────────────────────


def test_summarize_graph_is_valid_json_and_caps_nodes():
    graph = {
        "repo_url": "https://github.com/example/repo",
        "root_path": "/tmp/repo",
        "languages": ["python"],
        "entrypoints": ["app/main.py"],
        "manifests": {"requirements.txt": "fastapi\n"},
        "stats": {"node_count": 3},
        "nodes": [
            {"id": f"n{i}", "type": "module", "label": f"mod{i}", "summary": "x" * 500}
            for i in range(3)
        ],
        "edges": [{"source": "n0", "target": "n1", "type": "imports"}],
    }
    out = advise_mod.summarize_graph(graph, max_nodes=2, max_edges=10)
    data = json.loads(out)  # must be valid JSON
    assert data["node_count"] == 3
    assert len(data["nodes"]) == 2  # capped
    assert data["truncated"] is True
    assert len(data["nodes"][0]["summary"]) <= 200


def test_summarize_graph_caps_edges_too():
    graph = {
        "root_path": "/tmp/repo",
        "nodes": [{"id": "n0", "type": "module", "label": "mod0"}],
        "edges": [{"source": "n0", "target": "n0", "type": "imports"} for _ in range(10)],
    }
    out = advise_mod.summarize_graph(graph, max_nodes=10, max_edges=3)
    data = json.loads(out)
    assert data["edge_count"] == 10
    assert len(data["edges"]) == 3
    assert data["truncated"] is True


# ── summarize_architecture_report ────────────────────────────────────────────


def test_summarize_architecture_report_none_returns_none():
    assert advise_mod.summarize_architecture_report(None) is None


def test_summarize_architecture_report_caps_risks():
    report = {
        "summary": "A small service.",
        "components": [{"name": "API", "responsibility": "HTTP layer", "node_ids": ["n1"]}],
        "layers": ["API"],
        "data_flow": "Client -> API",
        "external_integrations": ["Postgres"],
        "risks": [f"risk {i}" for i in range(20)],
    }
    out = advise_mod.summarize_architecture_report(report, max_risks=5)
    assert out["summary"] == "A small service."
    assert len(out["risks"]) == 5
    assert out["components"][0]["name"] == "API"


# ── advise (mocked agent) ────────────────────────────────────────────────────


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


def test_advise_happy_path_uses_mocked_agent(monkeypatch):
    raw = json.dumps(_valid_report_dict())

    def fake_invoke(get_agent, messages):
        assert callable(get_agent)
        assert messages and messages[0]["role"] == "user"
        return {"messages": [_FakeMessage(raw)]}

    monkeypatch.setattr(advise_mod, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [{"id": "n1", "type": "module", "label": "app.main"}], "edges": []}
    report = advise_mod.advise(graph)

    assert report.tech_stack == ["Python", "FastAPI", "PostgreSQL"]
    assert len(report.recommendations) == 2
    assert report.quick_wins == ["rec-1"]


def test_advise_includes_architecture_report_in_prompt_when_given(monkeypatch):
    raw = json.dumps(_valid_report_dict())
    captured = {}

    def fake_invoke(get_agent, messages):
        captured["content"] = messages[0]["content"]
        return {"messages": [_FakeMessage(raw)]}

    monkeypatch.setattr(advise_mod, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [], "edges": []}
    arch_report = {
        "summary": "A monolith.",
        "components": [],
        "layers": [],
        "data_flow": "",
        "external_integrations": [],
        "mermaid": "",
        "risks": ["No tests."],
    }
    advise_mod.advise(graph, arch_report)

    assert "Existing ArchitectureReport" in captured["content"]
    assert "A monolith." in captured["content"]


def test_advise_agent_failure_returns_minimal_report(monkeypatch):
    def fake_invoke(get_agent, messages):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(advise_mod, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [], "edges": []}
    report = advise_mod.advise(graph)

    assert report.summary == ""
    assert len(report.recommendations) == 1
    assert report.recommendations[0].category == "risk"
    assert "Advisor invocation failed" in report.recommendations[0].rationale
