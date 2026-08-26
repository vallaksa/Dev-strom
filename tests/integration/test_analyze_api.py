"""Integration tests for the /analyze endpoints (app/api.py) via TestClient.

`app.cartographer.pipeline.analyze_repository_with_graph` and the analysis
store's save/get are monkeypatched directly on app.api's module namespace —
same pattern test_cartographer_api.py uses — so these tests never make a real
clone / LLM / DB call.
"""

import importlib.util

from app import api as api_module

_JOBS_AVAILABLE = importlib.util.find_spec("app.services.jobs") is not None


def _fake_analysis() -> dict:
    return {
        "id": "analysis-uuid",
        "status": "complete",
        "summary": "A FastAPI service that maps and analyzes repositories.",
        "mermaid": "flowchart TD\n  API[API] --> P[Pipeline]",
        "created_at": "2026-01-01T00:00:00+00:00",
        "repository": {
            "id": "repo-uuid", "url": "https://github.com/example/repo", "root_path": "/tmp/repo",
            "commit_sha": None, "language": "python", "languages": ["python"],
            "dependencies": [{"name": "fastapi", "ecosystem": "pypi", "source": "requirements.txt", "version": None}],
            "entrypoints": ["module:app/main.py"], "file_count": 4, "loc": 42,
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "findings": [
            {"id": "finding-1", "repository_id": "repo-uuid", "category": "scalability",
             "title": "Synchronous analysis blocks the request", "description": "…",
             "confidence": 0.75, "severity": "high",
             "evidence": [{"file": "app/api.py", "line_start": None, "line_end": None,
                           "symbol": "post_cartograph", "snippet": None,
                           "explanation": "clone+parse+LLM run before the response"}]},
        ],
        "recommendations": [
            {"id": "rec-1", "finding_id": "finding-1", "type": "scalability",
             "title": "Move analysis to a background job", "description": "…",
             "impact": "high", "effort": "medium", "priority": 1},
        ],
    }


def _fake_graph() -> dict:
    return {
        "repo_url": "https://github.com/example/repo", "root_path": "/tmp/repo",
        "languages": ["python"],
        "nodes": [{"id": "n1", "type": "module", "label": "app.main", "path": "app/main.py"}],
        "edges": [{"source": "n1", "target": "n1", "type": "imports"}],
        "entrypoints": ["module:app/main.py"], "manifests": {}, "stats": {"files": 4},
    }


def _install_fake_jobs(monkeypatch) -> dict:
    store: dict[str, dict] = {}

    def _create_job(kind: str, params: dict) -> str:
        job_id = f"job-{len(store) + 1}"
        store[job_id] = {"job_id": job_id, "kind": kind, "status": "pending",
                         "params": params, "result": None, "error": None}
        return job_id

    def _run_job(job_id: str, fn) -> None:
        store[job_id]["status"] = "running"
        try:
            store[job_id]["result"] = fn()
            store[job_id]["status"] = "done"
        except Exception as exc:  # pragma: no cover - exercised via the error test
            store[job_id]["error"] = str(exc)
            store[job_id]["status"] = "error"

    monkeypatch.setattr(api_module, "create_job", _create_job)
    monkeypatch.setattr(api_module, "get_job", store.get)
    monkeypatch.setattr(api_module, "run_job", _run_job)
    return store


def _patch_pipeline(monkeypatch, analysis=None, graph=None, run_id="analysis-run-1"):
    analysis = analysis if analysis is not None else _fake_analysis()
    graph = graph if graph is not None else _fake_graph()
    calls = {}

    def fake_pipeline(target, repo_url=None):
        calls["target"] = target
        calls["repo_url"] = repo_url
        return analysis, graph

    def fake_save(a, project_graph=None, repo_url=None):
        calls["saved_graph"] = project_graph
        calls["saved_repo_url"] = repo_url
        return run_id

    monkeypatch.setattr(api_module, "analyze_repository_with_graph", fake_pipeline)
    monkeypatch.setattr(api_module, "save_analysis_run", fake_save)
    return calls


# ── POST /analyze ─────────────────────────────────────────────────────────────

def test_analyze_happy_path_returns_flat_analysis_plus_graph(client, monkeypatch):
    _patch_pipeline(monkeypatch)
    resp = client.post("/analyze", json={"repo_url": "https://github.com/example/repo"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "analysis-run-1"
    # Analysis fields are flattened to the top level (Orion's contract)
    assert body["status"] == "complete"
    assert body["summary"].startswith("A FastAPI service")
    assert body["repository"]["language"] == "python"
    assert body["findings"][0]["evidence"][0]["file"] == "app/api.py"
    assert body["recommendations"][0]["finding_id"] == "finding-1"
    # UI extras: graph (structural) + mermaid (from the Analysis) flow through
    assert body["graph"]["nodes"][0]["id"] == "n1"
    assert body["mermaid"].startswith("flowchart TD")


def test_analyze_local_path_passes_path_as_target(client, monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    resp = client.post("/analyze", json={"path": "/local/repo"})

    assert resp.status_code == 200
    assert calls["target"] == "/local/repo"
    assert calls["repo_url"] is None
    # graph is persisted alongside the analysis
    assert calls["saved_graph"]["nodes"][0]["id"] == "n1"


def test_analyze_requires_at_least_one_source(client):
    assert client.post("/analyze", json={}).status_code == 422


def test_analyze_rejects_both_sources(client):
    resp = client.post("/analyze", json={"repo_url": "https://github.com/example/repo", "path": "/x"})
    assert resp.status_code == 422


def test_analyze_missing_openai_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module.settings, "openai_api_key", None)
    resp = client.post("/analyze", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_analyze_core_modules_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "analyze_repository_with_graph", None)
    monkeypatch.setattr(api_module, "save_analysis_run", None)
    resp = client.post("/analyze", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_analyze_pipeline_failure_returns_500(client, monkeypatch):
    def boom(target, repo_url=None):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(api_module, "analyze_repository_with_graph", boom)
    monkeypatch.setattr(api_module, "save_analysis_run", lambda a, project_graph=None, repo_url=None: "x")
    resp = client.post("/analyze", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 500


def test_analyze_core_modules_wired_on_import():
    assert api_module.analyze_repository_with_graph is not None
    assert api_module.save_analysis_run is not None
    assert api_module.get_analysis_run is not None


# ── POST /analyze?async=true ──────────────────────────────────────────────────

def test_analyze_async_returns_202_and_job_completes(client, monkeypatch):
    _patch_pipeline(monkeypatch, run_id="analysis-run-async")
    _install_fake_jobs(monkeypatch)

    resp = client.post("/analyze", params={"async": "true"},
                       json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"

    record = api_module.get_job(body["job_id"])
    assert record["status"] == "done"
    assert record["result"]["run_id"] == "analysis-run-async"
    assert record["result"]["graph"]["nodes"][0]["id"] == "n1"


def test_analyze_async_job_records_error_on_pipeline_failure(client, monkeypatch):
    def boom(target, repo_url=None):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(api_module, "analyze_repository_with_graph", boom)
    monkeypatch.setattr(api_module, "save_analysis_run", lambda a, project_graph=None, repo_url=None: "x")
    _install_fake_jobs(monkeypatch)

    resp = client.post("/analyze", params={"async": "true"},
                       json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 202
    record = api_module.get_job(resp.json()["job_id"])
    assert record["status"] == "error"
    assert "clone failed" in record["error"]


# ── GET /analyze/{run_id} ─────────────────────────────────────────────────────

def test_get_analyze_run_reloads_same_flat_shape(client, monkeypatch):
    record = {
        "run_id": "analysis-run-1", "repo_url": "https://github.com/example/repo",
        "analysis": _fake_analysis(), "project_graph": _fake_graph(),
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr(api_module, "get_analysis_run", lambda run_id: record)

    resp = client.get("/analyze/analysis-run-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "analysis-run-1"
    assert body["summary"].startswith("A FastAPI service")
    assert body["findings"][0]["id"] == "finding-1"
    assert body["graph"]["nodes"][0]["id"] == "n1"
    assert body["mermaid"].startswith("flowchart TD")


def test_get_analyze_run_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_analysis_run", lambda run_id: None)
    assert client.get("/analyze/nope").status_code == 404


def test_get_analyze_run_core_modules_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_analysis_run", None)
    assert client.get("/analyze/nope").status_code == 503


# ── GET /analyses (History list) ──────────────────────────────────────────────

def _summary_row(n: int) -> dict:
    return {
        "run_id": f"run-{n}", "repo_url": f"https://x/{n}.git", "language": "python",
        "status": "complete", "finding_count": n, "recommendation_count": n,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def test_list_analyses_happy_path(client, monkeypatch):
    monkeypatch.setattr(api_module, "list_analysis_runs",
                        lambda limit, offset: [_summary_row(1), _summary_row(2)])
    resp = client.get("/analyses")
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 20 and body["offset"] == 0
    assert [a["run_id"] for a in body["analyses"]] == ["run-1", "run-2"]
    assert body["analyses"][0]["finding_count"] == 1


def test_list_analyses_passes_pagination_through(client, monkeypatch):
    calls = {}
    monkeypatch.setattr(api_module, "list_analysis_runs",
                        lambda limit, offset: calls.update(limit=limit, offset=offset) or [])
    resp = client.get("/analyses", params={"limit": 5, "offset": 10})
    assert resp.status_code == 200
    assert calls == {"limit": 5, "offset": 10}
    assert resp.json() == {"analyses": [], "limit": 5, "offset": 10}


def test_list_analyses_rejects_out_of_range_limit(client):
    assert client.get("/analyses", params={"limit": 0}).status_code == 422
    assert client.get("/analyses", params={"limit": 101}).status_code == 422


def test_list_analyses_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "list_analysis_runs", None)
    assert client.get("/analyses").status_code == 503
