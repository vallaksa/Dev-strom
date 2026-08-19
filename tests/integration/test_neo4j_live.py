"""Live Neo4j round trip for /cartograph.

Skipped unless a Neo4j instance is reachable (local `docker compose up -d neo4j`).
CI stays hermetic: no live Neo4j, so this test skips rather than adding an
external dependency. Pipeline/LLM calls are monkeypatched; persistence is real.
"""

import os

import pytest
from neo4j import GraphDatabase

from app import api as api_module
from app.cartographer.model import ArchitectureReport, Edge, Node, ProjectGraph
from app.cartographer.store import Neo4jStore


def neo4j_reachable() -> bool:
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "devstrom")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return True
    except Exception:
        return False


def _graph() -> ProjectGraph:
    return ProjectGraph(
        repo_url="https://github.com/example/repo",
        root_path="/tmp/repo",
        languages=["python"],
        nodes=[
            Node(
                id="n1",
                type="module",
                label="app.main",
                path="app/main.py",
                language="python",
            ),
        ],
        edges=[Edge(source="n1", target="n1", type="imports")],
        entrypoints=["app/main.py"],
        manifests={"requirements.txt": "fastapi\n"},
        stats={"node_count": 1, "edge_count": 1},
    )


def _report() -> ArchitectureReport:
    return ArchitectureReport(
        summary="A small FastAPI service.",
        components=[{"name": "API", "responsibility": "HTTP layer", "node_ids": ["n1"]}],
        layers=["API"],
        data_flow="Client -> API -> DB",
        external_integrations=["PostgreSQL"],
        mermaid="flowchart TD\n  A[API] --> B[(DB)]",
        risks=[],
    )


@pytest.mark.skipif(not neo4j_reachable(), reason="no live Neo4j")
def test_cartograph_post_get_round_trip_neo4j(client, monkeypatch):
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "devstrom")
    store = Neo4jStore(uri=uri, user=user, password=password)
    graph = _graph()
    report = _report()

    monkeypatch.setattr(api_module, "cartograph", lambda target, repo_url=None: graph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", store.save)
    monkeypatch.setattr(api_module, "get_cartograph_run", store.get)

    post = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})
    assert post.status_code == 200
    body = post.json()
    run_id = body["run_id"]
    assert body["project_graph"]["repo_url"] == graph.repo_url
    assert body["architecture_report"]["summary"] == report.summary

    get = client.get(f"/cartograph/{run_id}")
    assert get.status_code == 200
    got = get.json()
    assert got["run_id"] == run_id
    restored = ProjectGraph.model_validate(got["project_graph"])
    assert restored.nodes[0].id == "n1"
    assert {e.type for e in restored.edges} == {"imports"}
    assert got["architecture_report"]["layers"] == ["API"]
    store.close()
