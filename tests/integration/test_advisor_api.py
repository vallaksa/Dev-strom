"""Integration tests for the /advise endpoints (app/api.py) via TestClient.

`app.advisor.{pipeline,store}` are monkeypatched directly on app.api's
module namespace - `advise_repo_with_context`, `save_advisor_run`,
`get_advisor_run` - the same pattern tests/integration/test_cartographer_api.py
uses for the F1 pipeline/store functions. This means these tests never
require a real clone/LLM/DB call.
"""

from app import api as api_module


def _fake_advisor_report() -> dict:
    return {
        "summary": "A small FastAPI service with thin test coverage.",
        "tech_stack": ["Python", "FastAPI"],
        "recommendations": [
            {
                "id": "rec-1",
                "category": "test",
                "title": "Add API integration tests",
                "rationale": "No test coverage evidenced for app/api.py.",
                "impact": "high",
                "effort": "low",
                "affected_node_ids": ["n1"],
                "suggested_steps": ["Add a TestClient-based test"],
            },
        ],
        "quick_wins": ["rec-1"],
        "strategic_bets": [],
    }


def _fake_pipeline_result(*, cartograph_run_id=None, repo_url=None) -> dict:
    return {
        "advisor_report": _fake_advisor_report(),
        "cartograph_run_id": cartograph_run_id,
        "repo_url": repo_url,
    }


# ── POST /advise ──────────────────────────────────────────────────────────────


def test_advise_happy_path_repo_url_returns_run_id_and_report(client, monkeypatch):
    calls = {}

    def fake_pipeline(url_or_path=None, run_id=None):
        calls["url_or_path"] = url_or_path
        calls["run_id"] = run_id
        return _fake_pipeline_result(repo_url="https://github.com/example/repo")

    monkeypatch.setattr(api_module, "advise_repo_with_context", fake_pipeline)
    monkeypatch.setattr(
        api_module, "save_advisor_run",
        lambda report, cartograph_run_id=None, repo_url=None: "advisor-run-1",
    )

    resp = client.post("/advise", json={"repo_url": "https://github.com/example/repo"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "advisor-run-1"
    assert body["advisor_report"] == _fake_advisor_report()
    assert calls["url_or_path"] == "https://github.com/example/repo"
    assert calls["run_id"] is None


def test_advise_happy_path_path_returns_run_id_and_report(client, monkeypatch):
    calls = {}

    def fake_pipeline(url_or_path=None, run_id=None):
        calls["url_or_path"] = url_or_path
        calls["run_id"] = run_id
        return _fake_pipeline_result(repo_url=None)

    monkeypatch.setattr(api_module, "advise_repo_with_context", fake_pipeline)
    monkeypatch.setattr(
        api_module, "save_advisor_run",
        lambda report, cartograph_run_id=None, repo_url=None: "advisor-run-path",
    )

    resp = client.post("/advise", json={"path": "/local/repo"})

    assert resp.status_code == 200
    assert calls["url_or_path"] == "/local/repo"
    assert calls["run_id"] is None


def test_advise_happy_path_via_run_id_returns_run_id_and_report(client, monkeypatch):
    calls = {}

    def fake_pipeline(url_or_path=None, run_id=None):
        calls["url_or_path"] = url_or_path
        calls["run_id"] = run_id
        return _fake_pipeline_result(cartograph_run_id="cartograph-run-1")

    save_calls = {}

    def fake_save(report, cartograph_run_id=None, repo_url=None):
        save_calls["cartograph_run_id"] = cartograph_run_id
        save_calls["repo_url"] = repo_url
        return "advisor-run-2"

    monkeypatch.setattr(api_module, "advise_repo_with_context", fake_pipeline)
    monkeypatch.setattr(api_module, "save_advisor_run", fake_save)

    resp = client.post("/advise", json={"run_id": "cartograph-run-1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "advisor-run-2"
    assert calls["url_or_path"] is None
    assert calls["run_id"] == "cartograph-run-1"
    assert save_calls["cartograph_run_id"] == "cartograph-run-1"


def test_advise_requires_at_least_one_source(client):
    resp = client.post("/advise", json={})
    assert resp.status_code == 422


def test_advise_rejects_multiple_sources(client):
    resp = client.post(
        "/advise",
        json={"repo_url": "https://github.com/example/repo", "run_id": "some-run-id"},
    )
    assert resp.status_code == 422


def test_advise_rejects_all_three_sources(client):
    resp = client.post(
        "/advise",
        json={
            "repo_url": "https://github.com/example/repo",
            "path": "/local/repo",
            "run_id": "some-run-id",
        },
    )
    assert resp.status_code == 422


def test_advise_core_modules_are_wired_on_import():
    """F2 landed: pipeline/store must actually import, not stay None behind
    the ImportError guard (that would 503 in prod)."""
    assert api_module.advise_repo_with_context is not None
    assert api_module.save_advisor_run is not None
    assert api_module.get_advisor_run is not None


def test_advise_missing_openai_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module.settings, "openai_api_key", None)
    resp = client.post("/advise", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_advise_core_modules_unavailable_returns_503(client, monkeypatch):
    """When app.advisor.{pipeline,store} aren't wired up, the endpoint
    returns a clear 503 instead of an ImportError/500."""
    monkeypatch.setattr(api_module, "advise_repo_with_context", None)
    monkeypatch.setattr(api_module, "save_advisor_run", None)

    resp = client.post("/advise", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 503


def test_advise_pipeline_failure_returns_500(client, monkeypatch):
    def boom(url_or_path=None, run_id=None):
        raise RuntimeError("clone failed")

    monkeypatch.setattr(api_module, "advise_repo_with_context", boom)
    monkeypatch.setattr(
        api_module, "save_advisor_run",
        lambda report, cartograph_run_id=None, repo_url=None: "unused",
    )

    resp = client.post("/advise", json={"repo_url": "https://github.com/example/repo"})
    assert resp.status_code == 500


# ── GET /advise/{run_id} ─────────────────────────────────────────────────────


def test_get_advise_run_happy_path(client, monkeypatch):
    record = {
        "run_id": "advisor-run-1",
        "cartograph_run_id": None,
        "repo_url": "https://github.com/example/repo",
        "advisor_report": _fake_advisor_report(),
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr(api_module, "get_advisor_run", lambda run_id: record)

    resp = client.get("/advise/advisor-run-1")

    assert resp.status_code == 200
    assert resp.json() == record


def test_get_advise_run_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_advisor_run", lambda run_id: None)
    resp = client.get("/advise/does-not-exist")
    assert resp.status_code == 404


def test_get_advise_run_core_modules_unavailable_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_advisor_run", None)
    resp = client.get("/advise/does-not-exist")
    assert resp.status_code == 503
