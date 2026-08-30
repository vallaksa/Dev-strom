"""Integration tests for the /cartograph endpoints (app/api.py) via TestClient.

`app.cartographer.{pipeline,analyze,store}` (owned by a parallel branch,
feat/f1-core) are monkeypatched directly on app.api's module namespace -
`cartograph`, `analyze_architecture`, `save_cartograph_run`,
`get_cartograph_run` - the same pattern tests/integration/test_api.py uses
for `graph_app` / `expand_idea`. This means these tests never require the
real app.cartographer package to exist and never make a real clone/LLM/DB
call, whether or not feat/f1-core has landed in this worktree yet.
"""

from app import api as api_module

import importlib.util

_JOBS_AVAILABLE = importlib.util.find_spec("app.services.jobs") is not None


def _install_fake_jobs(monkeypatch) -> dict:
    """app.services.jobs (real implementation) needs a live Postgres session
    - out of scope for these tests, which only exercise app.api's scheduling
    logic (create a job, hand it to BackgroundTasks, poll it). Swap in a
    tiny in-memory fake bound to api_module's imported names, same pattern
    this file already uses for save_cartograph_run/get_cartograph_run etc.
    Returns the backing dict for direct inspection if needed.
    """
    store: dict[str, dict] = {}

    def _create_job(kind: str, params: dict) -> str:
        job_id = f"job-{len(store) + 1}"
        store[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": "pending",
            "params": params,
            "result": None,
            "error": None,
        }
        return job_id

    def _fake_get_job(job_id: str) -> dict | None:
        return store.get(job_id)

    def _run_job(job_id: str, fn) -> None:
        store[job_id]["status"] = "running"
        try:
            store[job_id]["result"] = fn()
            store[job_id]["status"] = "done"
        except Exception as exc:  # pragma: no cover - exercised via the error test
            store[job_id]["error"] = str(exc)
            store[job_id]["status"] = "error"

    monkeypatch.setattr(api_module, "create_job", _create_job)
    monkeypatch.setattr(api_module, "get_job", _fake_get_job)
    monkeypatch.setattr(api_module, "run_job", _run_job)
    return store


def _fake_project_graph() -> dict:
    return {
        "repo_url": "https://github.com/example/repo",
        "root_path": "/tmp/repo",
        "languages": ["python"],
        "nodes": [
            {"id": "n1", "type": "module", "label": "app.main", "path": "app/main.py", "language": "python"},
        ],
        "edges": [{"source": "n1", "target": "n1", "type": "imports"}],
        "entrypoints": ["app/main.py"],
        "manifests": {"requirements.txt": "fastapi\n"},
        "stats": {"node_count": 1, "edge_count": 1},
    }


def _fake_architecture_report() -> dict:
    return {
        "summary": "A small FastAPI service.",
        "components": [{"name": "API", "responsibility": "HTTP layer", "node_ids": ["n1"]}],
        "layers": ["API"],
        "data_flow": "Client -> API -> DB",
        "external_integrations": ["PostgreSQL"],
        "mermaid": "flowchart TD\n  A[API] --> B[(DB)]",
        "risks": [],
    }


# ── POST /cartograph ─────────────────────────────────────────────────────────


def test_cartograph_happy_path_repo_url_returns_run_id_and_payload(client, monkeypatch):
    graph = _fake_project_graph()
    report = _fake_architecture_report()

    monkeypatch.setattr(api_module, "cartograph", lambda target, repo_url=None: graph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "cartograph-run-1")

    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "cartograph-run-1"
    assert body["project_graph"] == graph
    assert body["architecture_report"] == report


def test_cartograph_happy_path_local_path_passes_path_as_target(client, monkeypatch):
    graph = _fake_project_graph()
    report = _fake_architecture_report()
    calls = {}

    def fake_cartograph(target, repo_url=None):
        calls["target"] = target
        calls["repo_url"] = repo_url
        return graph

    monkeypatch.setattr(api_module, "cartograph", fake_cartograph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "cartograph-run-2")

    resp = client.post("/cartograph", json={"path": "/local/repo"})

    assert resp.status_code == 200
    assert calls["target"] == "/local/repo"
    assert calls["repo_url"] is None


def test_cartograph_requires_at_least_one_source(client):
    resp = client.post("/cartograph", json={})
    assert resp.status_code == 422


def test_cartograph_rejects_both_sources(client):
    resp = client.post(
        "/cartograph",
        json={"repo_url": "https://github.com/example/repo", "path": "/local/repo"},
    )
    assert resp.status_code == 422


def test_cartograph_core_modules_are_wired_on_import():
    """F1-core landed: pipeline/analyze/store must actually import, not stay None
    behind the parallel-branch ImportError guard (that produced a 503 in prod)."""
    assert api_module.cartograph is not None
    assert api_module.analyze_architecture is not None
    assert api_module.save_cartograph_run is not None
    assert api_module.get_cartograph_run is not None


def test_cartograph_store_uses_backend_factory():
    """API must pick Postgres vs Neo4j via get_cartograph_store(), not a hardcoded
    PostgresJsonbStore, so CARTOGRAPH_STORE_BACKEND=neo4j actually takes effect."""
    import inspect

    assert "get_cartograph_store" in inspect.getsource(api_module)


def test_cartograph_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module.settings, "api_key", None)
    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_cartograph_core_modules_unavailable_returns_503(client, monkeypatch):
    """When app.cartographer.{pipeline,analyze,store} haven't landed (the
    normal pre-integration state of this worktree), the endpoint returns a
    clear 503 instead of an ImportError/500."""
    monkeypatch.setattr(api_module, "cartograph", None)
    monkeypatch.setattr(api_module, "analyze_architecture", None)
    monkeypatch.setattr(api_module, "save_cartograph_run", None)

    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_cartograph_pipeline_failure_returns_500(client, monkeypatch):
    def boom(target, repo_url=None):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(api_module, "cartograph", boom)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: _fake_architecture_report())
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "unused")

    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 500


# ── POST /cartograph?async=true ──────────────────────────────────────────────


def test_cartograph_async_returns_202_with_job_id(client, monkeypatch):
    graph = _fake_project_graph()
    report = _fake_architecture_report()

    monkeypatch.setattr(api_module, "cartograph", lambda target, repo_url=None: graph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "cartograph-run-async")
    _install_fake_jobs(monkeypatch)

    resp = client.post(
        "/cartograph",
        params={"async": "true"},
        json={"repo_url": "https://github.com/example/repo"},
    )

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "pending"

    # TestClient runs BackgroundTasks synchronously right after the response
    # is generated, so the job should have already completed by the time we
    # get here. app.services.jobs itself is exercised separately (real
    # Postgres-backed implementation) in tests/unit/test_jobs.py; here we
    # only need app.api's scheduling logic against the same contract.
    record = api_module.get_job(body["job_id"])
    assert record is not None
    assert record["status"] == "done"
    assert record["result"]["run_id"] == "cartograph-run-async"
    assert record["result"]["project_graph"] == graph
    assert record["result"]["architecture_report"] == report


def test_cartograph_async_job_records_error_on_pipeline_failure(client, monkeypatch):
    def boom(target, repo_url=None):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(api_module, "cartograph", boom)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: _fake_architecture_report())
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "unused")
    _install_fake_jobs(monkeypatch)

    resp = client.post(
        "/cartograph",
        params={"async": "true"},
        json={"repo_url": "https://github.com/example/repo"},
    )

    # Scheduling always succeeds with 202 - the failure surfaces in the job.
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    record = api_module.get_job(job_id)
    assert record is not None
    assert record["status"] == "error"
    assert "clone failed" in record["error"]


def test_cartograph_async_missing_api_key_returns_503(client, monkeypatch):
    """Guard checks stay synchronous even in async mode - the caller learns
    immediately rather than polling a job that was doomed from the start."""
    monkeypatch.setattr(api_module.settings, "api_key", None)
    resp = client.post(
        "/cartograph",
        params={"async": "true"},
        json={"repo_url": "https://github.com/example/repo"},
    )
    assert resp.status_code == 503


def test_cartograph_async_core_modules_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "cartograph", None)
    monkeypatch.setattr(api_module, "analyze_architecture", None)
    monkeypatch.setattr(api_module, "save_cartograph_run", None)

    resp = client.post(
        "/cartograph",
        params={"async": "true"},
        json={"repo_url": "https://github.com/example/repo"},
    )
    assert resp.status_code == 503


def test_cartograph_sync_default_unchanged_when_async_omitted(client, monkeypatch):
    """No `async` query param at all still yields the original synchronous
    200 behavior - default behavior must not change."""
    graph = _fake_project_graph()
    report = _fake_architecture_report()

    monkeypatch.setattr(api_module, "cartograph", lambda target, repo_url=None: graph)
    monkeypatch.setattr(api_module, "analyze_architecture", lambda g: report)
    monkeypatch.setattr(api_module, "save_cartograph_run", lambda pg, ar: "cartograph-run-sync")

    resp = client.post("/cartograph", json={"repo_url": "https://github.com/example/repo"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "cartograph-run-sync"
    assert body["project_graph"] == graph
    assert body["architecture_report"] == report


# ── GET /jobs/{job_id} ────────────────────────────────────────────────────────


def test_get_job_not_found_returns_404(client):
    resp = client.get("/jobs/does-not-exist")
    assert resp.status_code in (404, 503)
    if not _JOBS_AVAILABLE:
        # If app.services.jobs isn't importable, the route 503s instead -
        # that's also correct behavior per the ImportError-guard pattern.
        assert resp.status_code == 503
    else:
        assert resp.status_code == 404


# ── GET /cartograph/{run_id} ─────────────────────────────────────────────────


def test_get_cartograph_run_happy_path(client, monkeypatch):
    record = {
        "run_id": "cartograph-run-1",
        "project_graph": _fake_project_graph(),
        "architecture_report": _fake_architecture_report(),
    }
    monkeypatch.setattr(api_module, "get_cartograph_run", lambda run_id: record)

    resp = client.get("/cartograph/cartograph-run-1")

    assert resp.status_code == 200
    assert resp.json() == record


def test_get_cartograph_run_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_cartograph_run", lambda run_id: None)
    resp = client.get("/cartograph/does-not-exist")
    assert resp.status_code == 404


def test_get_cartograph_run_core_modules_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_cartograph_run", None)
    resp = client.get("/cartograph/does-not-exist")
    assert resp.status_code == 503
