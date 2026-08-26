"""Contract tests: Orion-2 frontend API shapes vs FastAPI/Pydantic backends.

Mirrors `web/src/api/types.ts` (Orion-2): NL `intent` ideas request, rich idea
card fields, and ArchitectureReport `design_decisions`. Uses TestClient with
LLM/DB monkeypatched — no network.
"""

from pydantic import ValidationError
import pytest

from app import api as api_module
from app.cartographer.model import ArchitectureReport, Edge, Node, ProjectGraph
from app.models.domain import Idea, ProjectIdea
from app.models.dto import IdeasRequest
from tests.conftest import FakeGraphApp, make_idea


# ── IdeasRequest DTO (Orion intent contract) ─────────────────────────────────


def test_ideas_request_accepts_intent_without_tech_stack():
    body = IdeasRequest(intent="Build an event-driven payments platform with AI.", count=3)
    assert body.resolved_tech_stack.startswith("Build an event-driven")
    assert body.tech_stack is None


def test_ideas_request_accepts_legacy_tech_stack():
    body = IdeasRequest(tech_stack="Python, FastAPI", count=2)
    assert body.resolved_tech_stack == "Python, FastAPI"


def test_ideas_request_rejects_empty_intent_and_stack():
    with pytest.raises(ValidationError):
        IdeasRequest(count=1)


def test_ideas_request_prefers_explicit_tech_stack_over_intent():
    body = IdeasRequest(intent="natural language", tech_stack="Go, Kafka", count=1)
    assert body.resolved_tech_stack == "Go, Kafka"


# ── Rich Idea / ProjectIdea shapes ───────────────────────────────────────────


def test_project_idea_accepts_orion_rich_fields():
    idea = ProjectIdea(
        name="Payment Recovery",
        problem_statement="Recover failed payment flows.",
        why_it_fits=["Kafka: event backbone"],
        real_world_value="Reduces lost revenue.",
        implementation_plan=["Model events", "Add workers"],
        engineering_challenges=["Idempotency", "Event ordering"],
        architectural_intent="Event-sourced recovery with audit trail",
        tradeoffs=["Higher ops complexity for stronger guarantees"],
        business_value="Recover failed checkouts automatically",
    )
    dumped = idea.model_dump()
    assert dumped["engineering_challenges"] == ["Idempotency", "Event ordering"]
    assert dumped["architectural_intent"].startswith("Event-sourced")
    assert dumped["tradeoffs"]
    assert dumped["business_value"]


def test_domain_idea_model_for_persisted_platform_idea():
    idea = Idea(
        id="idea-1",
        run_id="run-1",
        title="Intelligent Payment Recovery",
        description="Automatically recover failed payment flows.",
        business_value="Less lost revenue",
        engineering_challenges=["Idempotency", "Retry semantics"],
        architecture="Outbox + workers + audit log",
    )
    assert idea.engineering_challenges[0] == "Idempotency"


# ── ArchitectureReport design_decisions (Orion Design tab) ───────────────────


def test_architecture_report_accepts_design_decisions():
    report = ArchitectureReport(
        summary="A FastAPI cartographer service.",
        design_decisions=[
            {
                "title": "Shallow clone for ingestion",
                "why": "Analysis only needs the tip tree.",
                "benefits": ["Fast clone", "Less disk"],
                "tradeoffs": ["No full history for blame"],
                "alternatives": ["Full clone", "GitHub API tree walk"],
            }
        ],
    )
    assert len(report.design_decisions) == 1
    assert report.design_decisions[0]["title"].startswith("Shallow")


def test_project_graph_round_trip_matches_frontend_node_edge_literals():
    graph = ProjectGraph(
        root_path="/tmp/repo",
        repo_url="https://github.com/example/repo",
        languages=["python"],
        nodes=[Node(id="module:app/main.py", type="module", label="main.py", path="app/main.py")],
        edges=[Edge(source="module:app/main.py", target="ext:requests", type="imports")],
        entrypoints=["module:app/main.py"],
    )
    dumped = graph.model_dump()
    assert dumped["nodes"][0]["type"] == "module"
    assert dumped["edges"][0]["type"] == "imports"


# ── HTTP contract: POST /ideas with Orion intent body ────────────────────────


def test_post_ideas_accepts_orion_intent_body(client, monkeypatch):
    captured = {}

    class CapturingGraph(FakeGraphApp):
        def invoke(self, inputs: dict) -> dict:
            captured["inputs"] = inputs
            return super().invoke(inputs)

    monkeypatch.setattr(
        api_module,
        "graph_app",
        CapturingGraph({"ideas": [make_idea(1)], "web_context": "ctx"}),
    )
    monkeypatch.setattr(api_module, "save_run", lambda **kwargs: "run-orion-intent")

    resp = client.post(
        "/ideas",
        json={
            "intent": "Challenging backend project with event-driven payments and AI.",
            "count": 1,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-orion-intent"
    assert body["ideas"][0]["pid"] == 1
    assert "name" in body["ideas"][0]
    assert "problem_statement" in body["ideas"][0]
    assert captured["inputs"]["tech_stack"].startswith("Challenging backend")


def test_post_ideas_still_accepts_legacy_tech_stack(client, monkeypatch):
    monkeypatch.setattr(
        api_module,
        "graph_app",
        FakeGraphApp({"ideas": [make_idea(1)], "web_context": "ctx"}),
    )
    monkeypatch.setattr(api_module, "save_run", lambda **kwargs: "run-legacy")

    resp = client.post("/ideas", json={"tech_stack": "Python, FastAPI", "count": 1})
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run-legacy"


def test_post_ideas_rejects_body_without_intent_or_stack(client):
    resp = client.post("/ideas", json={"count": 2})
    assert resp.status_code == 422


def test_post_ideas_passthrough_rich_idea_fields(client, monkeypatch):
    rich = {
        **make_idea(1),
        "engineering_challenges": ["Idempotency", "Event ordering"],
        "architectural_intent": "Event-sourced recovery",
        "tradeoffs": ["Ops complexity"],
        "business_value": "Recover failed checkouts",
    }
    monkeypatch.setattr(
        api_module,
        "graph_app",
        FakeGraphApp({"ideas": [rich], "web_context": "ctx"}),
    )
    monkeypatch.setattr(api_module, "save_run", lambda **kwargs: "run-rich")

    resp = client.post(
        "/ideas",
        json={"intent": "payments + AI recovery", "count": 1},
    )
    assert resp.status_code == 200
    idea = resp.json()["ideas"][0]
    assert idea["engineering_challenges"] == ["Idempotency", "Event ordering"]
    assert idea["architectural_intent"] == "Event-sourced recovery"
    assert idea["tradeoffs"] == ["Ops complexity"]
    assert idea["business_value"] == "Recover failed checkouts"


# ── HTTP contract: cartograph response still validates against models ────────


def test_cartograph_response_includes_design_decisions_when_present(client, monkeypatch):
    graph = {
        "repo_url": "https://github.com/example/repo",
        "root_path": "/tmp/repo",
        "languages": ["python"],
        "nodes": [{"id": "n1", "type": "module", "label": "main", "path": "main.py"}],
        "edges": [],
        "entrypoints": [],
        "manifests": {},
        "stats": {},
    }
    report = {
        "summary": "svc",
        "components": [],
        "layers": [],
        "data_flow": "",
        "external_integrations": [],
        "mermaid": "",
        "risks": [],
        "design_decisions": [
            {
                "title": "JSON API",
                "why": "Frontend contract stability",
                "benefits": ["Typed clients"],
                "tradeoffs": ["Versioning discipline"],
            }
        ],
    }
    monkeypatch.setattr(api_module, "cartograph", lambda target, repo_url=None: graph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "carto-1")

    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["architecture_report"]["design_decisions"][0]["title"] == "JSON API"
    # Round-trip through the pydantic contract Orion consumes
    ArchitectureReport.model_validate(body["architecture_report"])
