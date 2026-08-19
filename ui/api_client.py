"""
HTTP client for the Dev-Strom FastAPI backend.
All Streamlit pages call these functions — never graph.py directly.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── shared request helpers ─────────────────────────────────────────────────────


def _post(path: str, payload: dict, *, timeout: int = 120) -> dict:
    """POST to the FastAPI server and return the parsed JSON body."""
    url = f"{API_BASE_URL}{path}"
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _get(path: str, *, params: dict | None = None, timeout: int = 30) -> dict:
    """GET from the FastAPI server and return the parsed JSON body."""
    url = f"{API_BASE_URL}{path}"
    response = httpx.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


# ── public API ─────────────────────────────────────────────────────────────────


def get_ideas(
    tech_stack: str,
    *,
    domain: str | None = None,
    level: str | None = None,
    count: int = 3,
    enable_multi_query: bool = False,
) -> dict:
    """Call POST /ideas and return {ideas: [...], run_id: str}."""
    payload: dict = {
        "tech_stack": tech_stack,
        "count": count,
        "enable_multi_query": enable_multi_query,
    }
    if domain and domain.strip():
        payload["domain"] = domain.strip()
    if level and level.strip():
        payload["level"] = level.strip()
    return _post("/ideas", payload, timeout=120)


def expand_idea(run_id: str, pid: int) -> dict:
    """Call POST /expand and return the expanded idea dict."""
    return _post("/expand", {"run_id": run_id, "pid": pid}, timeout=90)


def export_idea(run_id: str, pid: int) -> str:
    """Call POST /export and return the raw Markdown string."""
    url = f"{API_BASE_URL}/export"
    response = httpx.post(url, json={"run_id": run_id, "pid": pid}, timeout=30)
    response.raise_for_status()
    return response.text


def get_history(*, limit: int = 20, offset: int = 0) -> dict:
    """Call GET /history and return {runs: [...], limit, offset}."""
    return _get("/history", params={"limit": limit, "offset": offset})


def get_run_detail(run_id: str) -> dict:
    """Call GET /runs/{run_id} and return the full run including ideas."""
    return _get(f"/runs/{run_id}")


# ── Project Cartographer (F1) ────────────────────────────────────────────────


def post_cartograph(*, repo_url: str | None = None, path: str | None = None) -> dict:
    """Call POST /cartograph and return {run_id, project_graph, architecture_report}.

    Provide exactly one of repo_url or path. Uses a long timeout since the
    clone/parse/analyze pipeline runs synchronously on the server.
    """
    payload: dict = {}
    if repo_url and repo_url.strip():
        payload["repo_url"] = repo_url.strip()
    if path and path.strip():
        payload["path"] = path.strip()
    return _post("/cartograph", payload, timeout=300)


def get_cartograph_run(run_id: str) -> dict:
    """Call GET /cartograph/{run_id} and return {run_id, project_graph, architecture_report}."""
    return _get(f"/cartograph/{run_id}")


# ── Improvement / Feature Advisor (F2) ───────────────────────────────────────


def post_advise(
    *, repo_url: str | None = None, path: str | None = None, run_id: str | None = None
) -> dict:
    """Call POST /advise and return {run_id, advisor_report}.

    Provide exactly one of repo_url, path, or run_id. Uses a long timeout
    since (when not given run_id) the clone/parse/analyze/advise pipeline
    runs synchronously on the server.
    """
    payload: dict = {}
    if repo_url and repo_url.strip():
        payload["repo_url"] = repo_url.strip()
    if path and path.strip():
        payload["path"] = path.strip()
    if run_id and run_id.strip():
        payload["run_id"] = run_id.strip()
    return _post("/advise", payload, timeout=300)


def get_advise_run(run_id: str) -> dict:
    """Call GET /advise/{run_id} and return the persisted advisor run record."""
    return _get(f"/advise/{run_id}")

