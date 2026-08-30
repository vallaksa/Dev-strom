"""Tests for system-level graph aggregation."""

from app.cartographer.aggregate import to_system_graph
from app.cartographer.model import Edge, Node, ProjectGraph


def _sample_full_graph() -> ProjectGraph:
    return ProjectGraph(
        root_path="/tmp/repo",
        repo_url="https://github.com/example/repo",
        languages=["python", "typescript"],
        nodes=[
            Node(id="repo:repo", type="repo", label="repo", path="."),
            Node(id="package:app", type="package", label="app", path="app"),
            Node(id="module:app/api.py", type="module", label="api.py", path="app/api.py", language="python"),
            Node(id="module:app/graph.py", type="module", label="graph.py", path="app/graph.py", language="python"),
            Node(id="package:web", type="package", label="web", path="web"),
            Node(id="file:web/src/App.tsx", type="file", label="App.tsx", path="web/src/App.tsx", language="typescript"),
            Node(id="class:app/api.py:Router", type="class", label="Router", path="app/api.py"),
            Node(id="ext:psycopg2-binary", type="external_dep", label="psycopg2-binary"),
            Node(id="ext:fastapi", type="external_dep", label="fastapi"),
        ],
        edges=[
            Edge(source="repo:repo", target="package:app", type="contains"),
            Edge(source="repo:repo", target="package:web", type="contains"),
            Edge(source="module:app/api.py", target="ext:fastapi", type="imports"),
            Edge(source="module:app/api.py", target="ext:psycopg2-binary", type="imports"),
            Edge(source="module:app/api.py", target="module:app/graph.py", type="imports"),
        ],
        entrypoints=["module:app/api.py"],
        manifests={"requirements.txt": ["fastapi", "psycopg2-binary"]},
        stats={"files": 10},
    )


def test_to_system_graph_drops_class_and_file_noise():
    system = to_system_graph(_sample_full_graph())
    types = {n.type for n in system.nodes}
    assert "class" not in types
    assert "function" not in types
    assert "module" not in types
    assert "service" in types
    assert len(system.nodes) < len(_sample_full_graph().nodes)


def test_to_system_graph_creates_service_boundaries():
    system = to_system_graph(_sample_full_graph())
    service_ids = {n.id for n in system.nodes if n.type == "service"}
    assert "service:app" in service_ids
    assert "service:web" in service_ids


def test_to_system_graph_includes_architecture_patterns():
    system = to_system_graph(_sample_full_graph())
    patterns = system.stats.get("architecture_patterns", [])
    assert isinstance(patterns, list)
    assert len(patterns) >= 1
    assert system.stats.get("granularity") == "system"
