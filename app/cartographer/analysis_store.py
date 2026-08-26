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
        with get_session() as session:
            row = session.get(AnalysisRun, uuid.UUID(run_id))
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
        listing recent runs without the full JSONB payload."""
        with get_session() as session:
            stmt = (
                select(AnalysisRun)
                .order_by(AnalysisRun.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "run_id": str(r.id),
                    "repo_url": r.repo_url,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
