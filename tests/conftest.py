"""Shared pytest fixtures for the Dev-Strom test suite.

IMPORTANT: this module sets safe dummy env vars *before* any `app.*` module
is imported anywhere in the suite. `app/services/db.py` currently reads
`os.environ["DATABASE_URL"]` at import time (it will build a SQLAlchemy
engine lazily but does not open a real connection until a query runs), so a
dummy connection string here is enough to make every module importable
without a real Postgres instance, an API_KEY, or a TAVILY_API_KEY.
No test in this suite makes a real network or database call - the LLM
graph, the web-search tool, and the run_service/DB layer are always
monkeypatched in the tests that need them.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/devstrom_test")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import api as api_module  # noqa: E402
from app.config import settings as _settings  # noqa: E402


@pytest.fixture(autouse=True)
def _auth_disabled_by_default(monkeypatch):
    """Pin the login gate OFF for every test regardless of the developer's
    local .env. Tests that exercise auth opt back in via the `auth_on`
    fixture."""
    monkeypatch.setattr(_settings, "auth_enabled", False, raising=False)
    monkeypatch.setattr(_settings, "mock_auth", False, raising=False)


@pytest.fixture()
def client() -> TestClient:
    """A TestClient for the FastAPI app. No real DB/LLM calls are made by
    the app itself unless a test explicitly forgets to monkeypatch a
    dependency - if that happens the test should fail loudly rather than
    reach the network, since OPENAI/TAVILY keys are dummy values and
    DATABASE_URL points at a host tests never actually connect to.
    """
    return TestClient(api_module.api)


def make_idea(n: int = 1) -> dict:
    """Build a valid ProjectIdea-shaped dict for use in tests."""
    return {
        "name": f"Idea {n}",
        "pitch": f"Pitch for idea {n}.",
        "problem_statement": f"Problem statement {n}.",
        "why_it_fits": [f"Tech {n}: fits because of reason {n}."],
        "real_world_value": f"Saves time and money, scenario {n}.",
        "implementation_plan": [],
    }


@pytest.fixture()
def sample_idea() -> dict:
    return make_idea(1)


@pytest.fixture()
def sample_run(sample_idea) -> dict:
    """A run dict shaped like app.services.run_service.get_run()'s return value."""
    idea_with_pid = {**sample_idea, "pid": 1}
    return {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "tech_stack": "LangChain, LangGraph",
        "domain": None,
        "level": None,
        "count": 1,
        "enable_multi_query": False,
        "ideas": [idea_with_pid],
        "web_context": "some web search context",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


class FakeGraphApp:
    """Stand-in for the compiled LangGraph `app` object exposed by app.graph.

    Swapping in an instance of this (rather than monkeypatching `.invoke` on
    the real singleton) avoids poking at LangGraph's CompiledStateGraph
    internals and guarantees zero network/LLM calls.
    """

    def __init__(self, result: dict):
        self._result = result

    def invoke(self, inputs: dict) -> dict:
        return self._result
