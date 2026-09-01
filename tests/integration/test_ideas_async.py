"""Integration tests for POST /ideas?async=true and GET /jobs/{id}/events.

Mirrors tests/integration/test_analyze_api.py: the job runner and the LLM
graph are faked on app.api's namespace — no real DB / LLM call.
"""

import json

from app import api as api_module
from app.services.models import ANONYMOUS_USER_ID
from tests.conftest import FakeGraphApp, make_idea


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
        except Exception as exc:
            store[job_id]["error"] = str(exc)
            store[job_id]["status"] = "error"

    monkeypatch.setattr(api_module, "create_job", _create_job)
    monkeypatch.setattr(api_module, "get_job", store.get)
    monkeypatch.setattr(api_module, "run_job", _run_job)
    # The SSE poll path reads status only. These fakes always leave the job
    # terminal, so the stream is served from initial_record and never polls —
    # but patch it anyway so a future non-terminal test cannot reach a real DB.
    monkeypatch.setattr(
        api_module, "get_job_status", lambda job_id: (store.get(job_id) or {}).get("status")
    )
    return store


def _patch_ideas_graph(monkeypatch, ideas=None, run_id="ideas-run-1"):
    ideas = ideas if ideas is not None else [make_idea(1), make_idea(2)]
    monkeypatch.setattr(
        api_module,
        "graph_app",
        FakeGraphApp({"ideas": ideas, "web_context": "ctx"}),
    )
    monkeypatch.setattr(api_module, "save_run", lambda **kwargs: run_id)


def _parse_sse(body: str):
    """Parse an SSE body into (event, data_dict) tuples."""
    out = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        event = None
        data = None
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        out.append((event, data))
    return out


# ── POST /ideas?async=true ────────────────────────────────────────────────────

def test_ideas_async_returns_202_and_job_completes(client, monkeypatch):
    _patch_ideas_graph(monkeypatch, run_id="ideas-run-async")
    _install_fake_jobs(monkeypatch)

    resp = client.post("/ideas", params={"async": "true"},
                       json={"intent": "A payments backend", "tech_stack": "Python"})

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"

    record = api_module.get_job(body["job_id"])
    assert record["kind"] == "ideas"
    assert record["status"] == "done"
    assert [i["name"] for i in record["result"]["ideas"]] == ["Idea 1", "Idea 2"]
    assert record["result"]["run_id"] == "ideas-run-async"


def test_ideas_async_job_records_error_on_pipeline_failure(client, monkeypatch):
    class BoomGraphApp:
        def invoke(self, inputs):
            raise RuntimeError("llm exploded")

    monkeypatch.setattr(api_module, "graph_app", BoomGraphApp())
    _install_fake_jobs(monkeypatch)

    resp = client.post("/ideas", params={"async": "true"}, json={"intent": "x"})
    assert resp.status_code == 202
    record = api_module.get_job(resp.json()["job_id"])
    assert record["status"] == "error"
    assert "llm exploded" in record["error"]


def test_ideas_async_missing_llm_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(api_module.settings, "api_key", None)
    resp = client.post("/ideas", params={"async": "true"}, json={"intent": "x"})
    assert resp.status_code == 503


def test_ideas_async_create_job_failure_returns_503(client, monkeypatch):
    """Job-store failures must be 503, not 500.

    The web client only falls back to sync POST /ideas on 503. A 500
    (Postgres down, DATABASE_URL unset, jobs table missing) leaves the
    UI with no ideas even though the sync pipeline still works.
    """
    def _boom_create_job(kind: str, params: dict) -> str:
        raise RuntimeError("could not connect to server")

    monkeypatch.setattr(api_module, "create_job", _boom_create_job)
    monkeypatch.setattr(api_module, "run_job", lambda *a, **k: None)

    resp = client.post("/ideas", params={"async": "true"}, json={"intent": "x"})
    assert resp.status_code == 503


def test_ideas_sync_still_returns_200_with_ideas(client, monkeypatch):
    _patch_ideas_graph(monkeypatch, run_id="ideas-run-sync")

    resp = client.post("/ideas", json={"tech_stack": "Python, FastAPI"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "ideas-run-sync"
    assert len(body["ideas"]) == 2
    assert body["ideas"][0]["pid"] == 1


# ── GET /jobs/{job_id}/events ─────────────────────────────────────────────────

def _completed_job(client, monkeypatch):
    _patch_ideas_graph(monkeypatch, run_id="ideas-run-sse")
    store = _install_fake_jobs(monkeypatch)
    resp = client.post("/ideas", params={"async": "true"}, json={"intent": "x"})
    return resp.json()["job_id"], store


def test_events_stream_done_for_completed_job(client, monkeypatch):
    job_id, _store = _completed_job(client, monkeypatch)

    with client.stream("GET", f"/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["x-accel-buffering"] == "no"
        assert "no-cache" in resp.headers["cache-control"]
        body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse(body)
    assert events[-1][0] == "done"
    assert events[-1][1]["run_id"] == "ideas-run-sse"


def test_events_unknown_job_returns_404(client, monkeypatch):
    _install_fake_jobs(monkeypatch)
    assert client.get("/jobs/nope/events").status_code == 404


def test_events_other_users_job_returns_404(client, monkeypatch):
    job_id, store = _completed_job(client, monkeypatch)
    # Simulate ownership: job params carry a different user_id than the caller.
    for record in store.values():
        record["params"]["user_id"] = "someone-else"
    assert client.get(f"/jobs/{job_id}/events").status_code == 404


def test_events_anonymous_owned_job_is_visible(client, monkeypatch):
    """A job explicitly owned by the anonymous user is the caller's own job.

    Regression test for the ownership comparison: `params` round-trips through
    JSONB so `user_id` is a str, while ANONYMOUS_USER_ID is a uuid.UUID — a
    direct `!=` between them is always True, which 404s a job for its rightful
    owner. test_events_other_users_job_returns_404 above passes either way
    (the types never match), so it is this test that pins the fix.
    """
    job_id, store = _completed_job(client, monkeypatch)
    for record in store.values():
        record["params"]["user_id"] = str(ANONYMOUS_USER_ID)

    with client.stream("GET", f"/jobs/{job_id}/events") as stream_resp:
        assert stream_resp.status_code == 200
        body = "".join(chunk for chunk in stream_resp.iter_text())

    assert _parse_sse(body)[-1][0] == "done"


def test_jobs_detail_other_users_job_returns_404(client, monkeypatch):
    """GET /jobs/{id} returns full params and result, so it needs the same gate."""
    job_id, store = _completed_job(client, monkeypatch)
    for record in store.values():
        record["params"]["user_id"] = "someone-else"
    assert client.get(f"/jobs/{job_id}").status_code == 404


def test_jobs_detail_anonymous_owned_job_is_visible(client, monkeypatch):
    job_id, store = _completed_job(client, monkeypatch)
    for record in store.values():
        record["params"]["user_id"] = str(ANONYMOUS_USER_ID)
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id


def test_events_error_job_streams_error_event(client, monkeypatch):
    class BoomGraphApp:
        def invoke(self, inputs):
            raise RuntimeError("boom")

    monkeypatch.setattr(api_module, "graph_app", BoomGraphApp())
    _install_fake_jobs(monkeypatch)
    resp = client.post("/ideas", params={"async": "true"}, json={"intent": "x"})
    job_id = resp.json()["job_id"]


    with client.stream("GET", f"/jobs/{job_id}/events") as stream_resp:
        body = "".join(chunk for chunk in stream_resp.iter_text())

    events = _parse_sse(body)
    assert events[-1][0] == "error"
    assert "boom" in events[-1][1]["error"]
