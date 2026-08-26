"""Unit tests for the pure summary projection used by the /analyses list
endpoint (app.cartographer.analysis_store.summarize_analysis_row).

Pure/DB-free: the round-trip through Postgres is covered separately (and
needs a live DB); here we only pin the JSONB -> summary-row shape, including
graceful defaults on partial/legacy payloads.
"""

from app.cartographer.analysis_store import PostgresJsonbStore, summarize_analysis_row


def test_get_malformed_run_id_returns_none_without_db():
    """A non-UUID run_id must resolve to None (-> 404 at the route), not raise
    a ValueError/500. Returns before any DB session is opened."""
    assert PostgresJsonbStore().get("not-a-uuid") is None


def _full_analysis() -> dict:
    return {
        "status": "complete",
        "repository": {"language": "python"},
        "findings": [{"id": "finding-1"}, {"id": "finding-2"}],
        "recommendations": [{"id": "rec-1"}],
    }


def test_summarize_full_analysis():
    row = summarize_analysis_row("run-1", "https://x/y.git", _full_analysis(), "2026-01-01T00:00:00+00:00")
    assert row == {
        "run_id": "run-1",
        "repo_url": "https://x/y.git",
        "language": "python",
        "status": "complete",
        "finding_count": 2,
        "recommendation_count": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def test_summarize_defaults_on_empty_analysis():
    row = summarize_analysis_row("run-2", None, {}, "2026-01-01T00:00:00+00:00")
    assert row["language"] is None
    assert row["status"] is None
    assert row["finding_count"] == 0
    assert row["recommendation_count"] == 0


def test_summarize_defaults_on_none_analysis():
    row = summarize_analysis_row("run-3", None, None, "2026-01-01T00:00:00+00:00")
    assert row["finding_count"] == 0
    assert row["recommendation_count"] == 0
    assert row["language"] is None


def test_summarize_tolerates_null_arrays():
    partial = {"status": "failed", "repository": None, "findings": None, "recommendations": None}
    row = summarize_analysis_row("run-4", None, partial, "2026-01-01T00:00:00+00:00")
    assert row["status"] == "failed"
    assert row["language"] is None
    assert row["finding_count"] == 0
