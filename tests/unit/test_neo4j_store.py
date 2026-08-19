"""Unit tests for app.cartographer.store.Neo4jStore.

Hermetic: no real Neo4j instance is available in this test environment (see
tests/conftest.py's project-wide "zero real network/DB connections"
convention), so the `neo4j` driver is mocked throughout. Two mocking
strategies are used:

  * A plain `MagicMock` driver/session for tests that only need to assert
    *which* Cypher was issued and with what parameter shape (save() call
    structure, missing-config errors, the Cypher-injection guard).
  * A small in-memory `FakeDriver`/`FakeSession` that actually interprets
    the handful of Cypher statements Neo4jStore issues (by matching on
    query text) and stores/returns data from a plain dict - this lets the
    save() -> get() round trip be exercised for real without a live
    database, which is the important correctness check: the reconstructed
    `project_graph` dict must validate against the real `ProjectGraph`
    pydantic model.
"""

import json
import re
from unittest.mock import MagicMock, patch

import pytest

from app.cartographer.model import Edge, Node, ProjectGraph
from app.cartographer.store import Neo4jStore, get_cartograph_store


def make_project_graph() -> ProjectGraph:
    nodes = [
        Node(
            id="module:app/api.py",
            type="module",
            label="app/api.py",
            path="app/api.py",
            language="python",
            summary="FastAPI entrypoint.",
            meta={"loc": 120, "tags": ["api", "http"]},
        ),
        Node(
            id="module:app/graph.py",
            type="module",
            label="app/graph.py",
            path="app/graph.py",
            language="python",
            summary=None,
            meta={},
        ),
        Node(
            id="ext:langgraph",
            type="external_dep",
            label="langgraph",
            meta={"version": ">=1.0"},
        ),
    ]
    edges = [
        Edge(source="module:app/api.py", target="module:app/graph.py", type="imports", meta={"line": 13}),
        Edge(source="module:app/graph.py", target="ext:langgraph", type="depends_on", meta={}),
    ]
    return ProjectGraph(
        repo_url="https://example.com/org/repo.git",
        root_path="/tmp/repo",
        languages=["python"],
        nodes=nodes,
        edges=edges,
        entrypoints=["app/api.py"],
        manifests={"requirements.txt": ["fastapi>=0.115"]},
        stats={"file_count": 3},
    )


# ── config / lazy-connection behavior ───────────────────────────────────────


def test_no_uri_raises_clear_error_on_save():
    with patch("app.cartographer.store.settings") as mock_settings:
        mock_settings.neo4j_uri = None
        mock_settings.neo4j_user = None
        mock_settings.neo4j_password = None
        store = Neo4jStore(uri=None, user=None, password=None)
        with pytest.raises(RuntimeError, match="NEO4J_URI"):
            store.save(make_project_graph())


def test_no_uri_raises_clear_error_on_get():
    with patch("app.cartographer.store.settings") as mock_settings:
        mock_settings.neo4j_uri = None
        mock_settings.neo4j_user = None
        mock_settings.neo4j_password = None
        store = Neo4jStore(uri=None, user=None, password=None)
        with pytest.raises(RuntimeError, match="NEO4J_URI"):
            store.get("some-run-id")


def test_construction_does_not_connect():
    """Instantiating Neo4jStore must never touch the network - the driver is
    created lazily on first save()/get() call, mirroring app.services.db's
    lazy engine pattern."""
    with patch("neo4j.GraphDatabase.driver") as mock_driver_factory:
        Neo4jStore(uri="neo4j://localhost:7687", user="neo4j", password="pw")
        mock_driver_factory.assert_not_called()


# ── save(): Cypher-building / call structure ────────────────────────────────


def _mock_driver_and_session():
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_driver.session.return_value.__exit__.return_value = False
    return mock_driver, mock_session


def test_save_returns_string_run_id_and_issues_expected_calls():
    graph = make_project_graph()
    mock_driver, mock_session = _mock_driver_and_session()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687", user="neo4j", password="pw")
        run_id = store.save(graph)

    assert isinstance(run_id, str)
    assert run_id  # non-empty

    calls = mock_session.run.call_args_list
    # 1 CartographRun + 3 GraphNode MERGEs + 2 relationship CREATEs
    assert len(calls) == 1 + len(graph.nodes) + len(graph.edges)

    run_call = calls[0]
    assert "CartographRun" in run_call.args[0]
    assert run_call.kwargs["id"] == run_id
    assert run_call.kwargs["repo_url"] == graph.repo_url
    assert run_call.kwargs["root_path"] == graph.root_path
    assert run_call.kwargs["languages"] == graph.languages
    assert run_call.kwargs["entrypoints"] == graph.entrypoints
    assert json.loads(run_call.kwargs["manifests"]) == graph.manifests
    assert json.loads(run_call.kwargs["stats"]) == graph.stats
    assert run_call.kwargs["architecture_report"] is None

    node_calls = calls[1 : 1 + len(graph.nodes)]
    for node, call in zip(graph.nodes, node_calls):
        assert "GraphNode" in call.args[0]
        assert call.kwargs["run_key"] == f"{run_id}:{node.id}"
        assert call.kwargs["orig_id"] == node.id
        assert call.kwargs["type"] == node.type
        assert json.loads(call.kwargs["meta"]) == node.meta

    edge_calls = calls[1 + len(graph.nodes) :]
    for edge, call in zip(graph.edges, edge_calls):
        cypher = call.args[0]
        assert f"`{edge.type}`" in cypher
        assert call.kwargs["source_key"] == f"{run_id}:{edge.source}"
        assert call.kwargs["target_key"] == f"{run_id}:{edge.target}"
        assert json.loads(call.kwargs["meta"]) == edge.meta


def test_save_with_architecture_report_serializes_it():
    from app.cartographer.model import ArchitectureReport

    graph = make_project_graph()
    report = ArchitectureReport(summary="A test system.", layers=["api", "domain"])
    mock_driver, mock_session = _mock_driver_and_session()

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687")
        store.save(graph, architecture_report=report)

    run_call = mock_session.run.call_args_list[0]
    stored_report = json.loads(run_call.kwargs["architecture_report"])
    assert stored_report["summary"] == "A test system."
    assert stored_report["layers"] == ["api", "domain"]


def test_save_rejects_unknown_edge_type_before_issuing_cypher():
    """Guards against Cypher injection via the interpolated relationship
    type: an edge.type outside the known EdgeType literals must be rejected
    before any Cypher string is built with it. Bypasses pydantic validation
    (which would normally reject this at Edge-construction time) via
    model_construct, to simulate a malformed/adversarial value reaching
    save() directly."""
    graph = make_project_graph()
    bad_edge = Edge.model_construct(
        source="module:app/api.py",
        target="module:app/graph.py",
        type="imports`]->(x) DETACH DELETE x //",
        meta={},
    )
    graph.edges.append(bad_edge)

    mock_driver, mock_session = _mock_driver_and_session()
    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687")
        with pytest.raises(ValueError, match="Unknown edge type"):
            store.save(graph)

    # No relationship-creating Cypher for the malicious edge was ever run.
    for call in mock_session.run.call_args_list:
        assert "DETACH DELETE" not in call.args[0]


# ── get(): empty result ─────────────────────────────────────────────────────


def test_get_returns_none_when_run_not_found():
    mock_driver, mock_session = _mock_driver_and_session()
    mock_session.run.return_value.single.return_value = None

    with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687")
        result = store.get("00000000-0000-0000-0000-000000000000")

    assert result is None


# ── in-memory fake driver for a real save() -> get() round trip ────────────


class _FakeRecord:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeResult:
    def __init__(self, records: list[_FakeRecord]):
        self._records = records

    def __iter__(self):
        return iter(self._records)

    def single(self):
        return self._records[0] if self._records else None


class FakeSession:
    """Interprets the small, fixed set of Cypher statements Neo4jStore
    issues, backed by a plain dict shared across the lifetime of one
    FakeDriver - just enough to exercise a real save() -> get() round trip.
    """

    def __init__(self, db: dict):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query: str, **params):
        if "CREATE (r:CartographRun" in query:
            self.db["run"] = dict(params)
            self.db.setdefault("nodes", {})
            self.db.setdefault("rels", [])
            return _FakeResult([])

        if "MERGE (n:GraphNode" in query:
            self.db["nodes"][params["run_key"]] = dict(params)
            return _FakeResult([])

        if re.search(r"CREATE \(a\)-\[rel:`", query):
            m = re.search(r"rel:`([^`]+)`", query)
            self.db["rels"].append(
                {
                    "source_key": params["source_key"],
                    "target_key": params["target_key"],
                    "type": m.group(1),
                    "meta": params["meta"],
                }
            )
            return _FakeResult([])

        if "MATCH (r:CartographRun {id: $run_id}) RETURN r" in query:
            run = self.db.get("run")
            if run is None or run["id"] != params["run_id"]:
                return _FakeResult([])
            return _FakeResult([_FakeRecord({"r": run})])

        if "HAS_NODE" in query and "RETURN n" in query:
            run_id = params["run_id"]
            recs = [
                _FakeRecord({"n": n})
                for key, n in self.db["nodes"].items()
                if key.startswith(f"{run_id}:")
            ]
            return _FakeResult(recs)

        if "MATCH (a:GraphNode)-[rel]->(b:GraphNode)" in query:
            prefix = params["prefix"]
            recs = []
            for rel in self.db["rels"]:
                if rel["source_key"].startswith(prefix) and rel["target_key"].startswith(prefix):
                    a = self.db["nodes"][rel["source_key"]]
                    b = self.db["nodes"][rel["target_key"]]
                    recs.append(
                        _FakeRecord(
                            {
                                "source": a["orig_id"],
                                "rel_type": rel["type"],
                                "target": b["orig_id"],
                                "meta": rel["meta"],
                            }
                        )
                    )
            return _FakeResult(recs)

        raise AssertionError(f"FakeSession received an unexpected query: {query}")


class FakeDriver:
    def __init__(self):
        self.db: dict = {}

    def session(self):
        return FakeSession(self.db)

    def close(self):
        pass


def test_save_then_get_round_trip_validates_against_project_graph_model():
    graph = make_project_graph()
    fake_driver = FakeDriver()

    with patch("neo4j.GraphDatabase.driver", return_value=fake_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687", user="neo4j", password="pw")
        run_id = store.save(graph)
        result = store.get(run_id)

    assert result is not None
    assert result["run_id"] == run_id
    assert result["repo_url"] == graph.repo_url
    assert result["root_path"] == graph.root_path
    assert result["architecture_report"] is None
    assert result["created_at"]  # ISO string, non-empty

    # The important correctness check: the reconstructed project_graph dict
    # must round-trip through real ProjectGraph pydantic validation.
    rebuilt = ProjectGraph(**result["project_graph"])

    assert rebuilt.repo_url == graph.repo_url
    assert rebuilt.root_path == graph.root_path
    assert rebuilt.languages == graph.languages
    assert rebuilt.entrypoints == graph.entrypoints
    assert rebuilt.manifests == graph.manifests
    assert rebuilt.stats == graph.stats

    assert {n.id for n in rebuilt.nodes} == {n.id for n in graph.nodes}
    rebuilt_by_id = {n.id: n for n in rebuilt.nodes}
    for original in graph.nodes:
        got = rebuilt_by_id[original.id]
        assert got.type == original.type
        assert got.label == original.label
        assert got.path == original.path
        assert got.language == original.language
        assert got.summary == original.summary
        assert got.meta == original.meta

    assert len(rebuilt.edges) == len(graph.edges)
    rebuilt_edges = {(e.source, e.target, e.type) for e in rebuilt.edges}
    original_edges = {(e.source, e.target, e.type) for e in graph.edges}
    assert rebuilt_edges == original_edges
    rebuilt_meta_by_pair = {(e.source, e.target): e.meta for e in rebuilt.edges}
    for original in graph.edges:
        assert rebuilt_meta_by_pair[(original.source, original.target)] == original.meta


def test_save_then_get_round_trip_with_architecture_report():
    from app.cartographer.model import ArchitectureReport

    graph = make_project_graph()
    report = ArchitectureReport(
        summary="Layered FastAPI service.",
        components=[{"name": "api", "responsibility": "HTTP layer", "node_ids": ["module:app/api.py"]}],
        layers=["api", "domain"],
        mermaid="graph TD; A-->B;",
    )
    fake_driver = FakeDriver()

    with patch("neo4j.GraphDatabase.driver", return_value=fake_driver):
        store = Neo4jStore(uri="neo4j://localhost:7687")
        run_id = store.save(graph, architecture_report=report)
        result = store.get(run_id)

    assert result["architecture_report"] is not None
    rebuilt_report = ArchitectureReport(**result["architecture_report"])
    assert rebuilt_report.summary == report.summary
    assert rebuilt_report.layers == report.layers
    assert rebuilt_report.mermaid == report.mermaid


# ── get_cartograph_store() factory ──────────────────────────────────────────


def test_get_cartograph_store_defaults_to_postgres():
    from app.cartographer.store import PostgresJsonbStore

    with patch("app.cartographer.store.settings") as mock_settings:
        mock_settings.cartograph_store_backend = "postgres"
        store = get_cartograph_store()
    assert isinstance(store, PostgresJsonbStore)


def test_get_cartograph_store_returns_neo4j_store():
    with patch("app.cartographer.store.settings") as mock_settings:
        mock_settings.cartograph_store_backend = "neo4j"
        mock_settings.neo4j_uri = "neo4j://localhost:7687"
        mock_settings.neo4j_user = None
        mock_settings.neo4j_password = None
        store = get_cartograph_store()
    assert isinstance(store, Neo4jStore)


def test_get_cartograph_store_rejects_unknown_backend():
    with patch("app.cartographer.store.settings") as mock_settings:
        mock_settings.cartograph_store_backend = "sqlite"
        with pytest.raises(ValueError, match="Unknown CARTOGRAPH_STORE_BACKEND"):
            get_cartograph_store()
