"""Unit tests for app/cartographer/analyze.py's JSON parsing/validation and
the mockable agent-invocation path.

`app.cartographer.model` (ProjectGraph/ArchitectureReport) is owned by a
parallel branch (feat/f1-core, building app/cartographer/{model,ingest,
parse,store,pipeline}.py) and may not exist yet in this worktree.
app.cartographer.analyze only imports it lazily (inside functions), so this
module installs a minimal in-memory stand-in for `app.cartographer.model`
into `sys.modules` (via monkeypatch, for the duration of each test) that
matches the pydantic contract described in the F1 task brief exactly:
ArchitectureReport{summary, components[{name,responsibility,node_ids[]}],
layers[], data_flow, external_integrations[], mermaid, risks[]}. No file
under app/cartographer/ is created by this stub - it exists purely in
sys.modules while a test runs. If the real module has already landed
(feat/f1-core merged into this worktree), the stub is skipped and these
tests exercise the real thing unmodified.
"""

import json
import sys
import types

import pytest
from pydantic import BaseModel


def _install_fake_cartographer_model(monkeypatch: pytest.MonkeyPatch) -> None:
    if "app.cartographer.model" in sys.modules:
        return  # real module already present (feat/f1-core landed) - use it as-is

    class Component(BaseModel):
        name: str
        responsibility: str
        node_ids: list[str] = []

    class ArchitectureReport(BaseModel):
        summary: str
        components: list[Component] = []
        layers: list[str] = []
        data_flow: str = ""
        external_integrations: list[str] = []
        mermaid: str = ""
        risks: list[str] = []

    fake_module = types.ModuleType("app.cartographer.model")
    fake_module.ArchitectureReport = ArchitectureReport
    fake_module.Component = Component
    monkeypatch.setitem(sys.modules, "app.cartographer.model", fake_module)


@pytest.fixture()
def analyze_mod(monkeypatch):
    """app.cartographer.analyze, with a fake app.cartographer.model installed
    so its lazy imports resolve without the real feat/f1-core module."""
    _install_fake_cartographer_model(monkeypatch)
    import app.cartographer.analyze as mod
    return mod


def _valid_report_dict() -> dict:
    return {
        "summary": "A small FastAPI service backed by Postgres.",
        "components": [
            {"name": "API", "responsibility": "HTTP layer", "node_ids": ["n1"]},
            {"name": "DB", "responsibility": "Persistence", "node_ids": ["n2"]},
        ],
        "layers": ["API", "Data"],
        "data_flow": "Client -> API -> DB",
        "external_integrations": ["PostgreSQL"],
        "mermaid": "flowchart TD\n  A[API] --> B[(DB)]",
        "risks": ["No integration tests found."],
    }


# ── parse_architecture_report ──────────────────────────────────────────────


def test_parse_architecture_report_valid_json(analyze_mod):
    raw = json.dumps(_valid_report_dict())
    report = analyze_mod.parse_architecture_report(raw)
    assert report.summary == "A small FastAPI service backed by Postgres."
    assert len(report.components) == 2
    assert report.components[0]["name"] == "API"
    assert report.mermaid.startswith("flowchart TD")
    assert report.risks == ["No integration tests found."]


def test_parse_architecture_report_strips_markdown_fences(analyze_mod):
    raw = "```json\n" + json.dumps(_valid_report_dict()) + "\n```"
    report = analyze_mod.parse_architecture_report(raw)
    assert report.summary == "A small FastAPI service backed by Postgres."


def test_parse_architecture_report_garbage_returns_minimal_report(analyze_mod):
    report = analyze_mod.parse_architecture_report("not json at all {{{")
    assert report.summary == ""
    assert report.components == []
    assert report.mermaid == ""
    assert len(report.risks) == 1
    assert "could not be parsed" in report.risks[0]


def test_parse_architecture_report_schema_mismatch_returns_minimal_report(analyze_mod):
    # Valid JSON, but missing the required "summary" field.
    raw = json.dumps({"components": []})
    report = analyze_mod.parse_architecture_report(raw)
    assert report.summary == ""
    assert report.mermaid == ""
    assert len(report.risks) == 1


def test_parse_architecture_report_preserves_design_decisions(analyze_mod):
    payload = {
        **_valid_report_dict(),
        "design_decisions": [
            {
                "title": "Shallow clone",
                "why": "Tip tree is enough for analysis",
                "benefits": ["Speed"],
                "tradeoffs": ["No history"],
                "alternatives": ["Full clone"],
            }
        ],
    }
    report = analyze_mod.parse_architecture_report(json.dumps(payload))
    assert len(report.design_decisions) == 1
    assert report.design_decisions[0]["title"] == "Shallow clone"


# ── summarize_graph ─────────────────────────────────────────────────────────


def test_summarize_graph_is_valid_json_and_caps_nodes(analyze_mod):
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
    out = analyze_mod.summarize_graph(graph, max_nodes=2, max_edges=10)
    data = json.loads(out)  # must be valid JSON
    assert data["node_count"] == 3
    assert len(data["nodes"]) == 2  # capped
    assert data["truncated"] is True
    assert len(data["nodes"][0]["summary"]) <= 200


# ── analyze_architecture (mocked agent) ──────────────────────────────────────


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


def test_analyze_architecture_happy_path_uses_mocked_agent(analyze_mod, monkeypatch):
    raw = json.dumps(_valid_report_dict())

    def fake_invoke(get_agent, messages):
        # get_agent must be callable (mirrors app.graph's contract) but we
        # never want a real agent/model call in a unit test.
        assert callable(get_agent)
        assert messages and messages[0]["role"] == "user"
        return {"messages": [_FakeMessage(raw)]}

    monkeypatch.setattr(analyze_mod, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [{"id": "n1", "type": "module", "label": "app.main"}], "edges": []}
    report = analyze_mod.analyze_architecture(graph)

    assert report.summary == "A small FastAPI service backed by Postgres."
    assert report.mermaid.startswith("flowchart TD")


def test_analyze_architecture_agent_failure_returns_minimal_report(analyze_mod, monkeypatch):
    def fake_invoke(get_agent, messages):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(analyze_mod, "_invoke_with_fallback", fake_invoke)

    graph = {"nodes": [], "edges": []}
    report = analyze_mod.analyze_architecture(graph)

    assert report.summary == ""
    assert report.mermaid == ""
    assert len(report.risks) == 1
    assert "Analysis failed" in report.risks[0]
