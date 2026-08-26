"""Pluggable persistence for evidence-first repository Analyses.

`AnalysisStore` is the interface the API/integration layer depends on;
`PostgresJsonbStore` is the concrete implementation, storing the domain
`Analysis` (and the structural `ProjectGraph` it was derived from) as JSONB
in the `analysis_runs` table. Mirrors `app.cartographer.store` /
`app.advisor.store` exactly (same interface shape, same `get_session`
usage) — see those modules for the rationale.
"""

import logging
import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select

from app.models.domain import Analysis
from app.services.db import get_session
from app.services.models import AnalysisRun

logger = logging.getLogger(__name__)


class AnalysisStore(ABC):
    """Persistence interface for repository-analysis runs.

    Implementations must round-trip an `Analysis` (plus the optional
    `ProjectGraph` it was derived from and the repo it targeted) through
    `save` -> `get`.
    """

    @abstractmethod
    def save(
        self,
        analysis: Analysis,
        *,
        project_graph: dict | None = None,
        repo_url: str | None = None,
    ) -> str:
        """Persist a run and return its run_id (as a string)."""
        raise NotImplementedError

    @abstractmethod
    def get(self, run_id: str) -> dict | None:
        """Fetch a run by id. Returns None if it doesn't exist.

        On success returns a dict with keys: run_id, repo_url, analysis
        (dict), project_graph (dict | None), created_at.
        """
        raise NotImplementedError


class PostgresJsonbStore(AnalysisStore):
    """Stores runs as JSONB rows in `analysis_runs`, via the existing lazy
    engine / get_session() pattern from app.services.db.
    """

    def save(
        self,
        analysis: Analysis,
        *,
        project_graph: dict | None = None,
        repo_url: str | None = None,
    ) -> str:
        row = AnalysisRun(
            repo_url=repo_url,
            analysis=analysis.model_dump(mode="json"),
            project_graph=project_graph,
        )
        with get_session() as session:
            session.add(row)
            session.flush()  # populate row.id before commit
            run_id = str(row.id)
        logger.info("Saved analysis run %s (repo_url=%s)", run_id, repo_url)
        return run_id

    def get(self, run_id: str) -> dict | None:
        try:
            key = uuid.UUID(run_id)
        except ValueError:
            # A malformed (non-UUID) id is simply "not found", not a 500 — the
            # /analyze/{run_id} route relies on None here to return its 404.
            return None
        with get_session() as session:
            row = session.get(AnalysisRun, key)
            if row is None:
                return None
            return {
                "run_id": str(row.id),
                "repo_url": row.repo_url,
                "analysis": row.analysis,
                "project_graph": row.project_graph,
                "created_at": row.created_at.isoformat(),
            }

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Convenience helper (not part of the AnalysisStore interface) for
        listing recent runs as lightweight SUMMARY rows for a History list:
        run_id, repo_url, language, status, finding/recommendation counts, and
        created_at — derived from the stored Analysis, not the full payload."""
        with get_session() as session:
            stmt = (
                select(AnalysisRun)
                .order_by(AnalysisRun.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [summarize_analysis_row(str(r.id), r.repo_url, r.analysis, r.created_at.isoformat()) for r in rows]


def summarize_analysis_row(run_id: str, repo_url: str | None, analysis: dict | None, created_at: str) -> dict:
    """Project a stored Analysis (JSONB dict) into a History-list summary row.

    Pure and defensive so it can be unit-tested without a DB and never raises
    on a partial/legacy payload: missing pieces default to null/0.
    """
    analysis = analysis or {}
    repository = analysis.get("repository") or {}
    return {
        "run_id": run_id,
        "repo_url": repo_url,
        "language": repository.get("language"),
        "status": analysis.get("status"),
        "finding_count": len(analysis.get("findings") or []),
        "recommendation_count": len(analysis.get("recommendations") or []),
        "created_at": created_at,
    }
