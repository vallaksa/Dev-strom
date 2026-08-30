"""Unit tests for advisor pipeline run loading (analysis first, cartograph fallback)."""

import uuid
from contextlib import contextmanager
from types import SimpleNamespace

from app.advisor import pipeline as pipeline_mod
from app.cartographer.model import ProjectGraph

_CARTOGRAPH_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _graph() -> dict:
    return {
        "repo_url": "https://github.com/vallaksa/journalApplication.git",
        "root_path": "/tmp/repo",
        "languages": ["java"],
        "nodes": [{"id": "n1", "type": "module", "label": "App"}],
        "edges": [],
        "entrypoints": [],
        "manifests": {},
        "stats": {},
    }


def test_load_from_run_prefers_analysis_store(monkeypatch):
    monkeypatch.setattr(
        "app.cartographer.analysis_store.PostgresJsonbStore.get",
        lambda self, run_id: {"project_graph": _graph()},
    )

    graph, report, cartograph_id = pipeline_mod._load_from_run("vallaksa-journalapplication")
    assert isinstance(graph, ProjectGraph)
    assert graph.repo_url == "https://github.com/vallaksa/journalApplication.git"
    assert report is None
    assert cartograph_id is None


def test_load_from_run_falls_back_to_cartograph(monkeypatch):
    monkeypatch.setattr(
        "app.cartographer.analysis_store.PostgresJsonbStore.get",
        lambda self, run_id: None,
    )

    @contextmanager
    def fake_session():
        yield object()

    row = SimpleNamespace(
        id=_CARTOGRAPH_UUID,
        project_graph=_graph(),
        architecture_report={"summary": "ok", "mermaid": ""},
    )
    monkeypatch.setattr(pipeline_mod, "get_session", fake_session)
    monkeypatch.setattr(pipeline_mod, "get_by_public_id", lambda session, model, run_id: row)

    graph, report, cartograph_id = pipeline_mod._load_from_run("vallaksa-journalapplication")
    assert graph.nodes[0].id == "n1"
    assert report is not None
    assert report.summary == "ok"
    assert cartograph_id == str(_CARTOGRAPH_UUID)


def test_load_from_run_missing_raises(monkeypatch):
    monkeypatch.setattr(
        "app.cartographer.analysis_store.PostgresJsonbStore.get",
        lambda self, run_id: None,
    )

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(pipeline_mod, "get_session", fake_session)
    monkeypatch.setattr(pipeline_mod, "get_by_public_id", lambda session, model, run_id: None)
    try:
        pipeline_mod._load_from_run("missing-run")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "missing-run" in str(exc)
