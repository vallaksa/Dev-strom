"""Pluggable persistence for Improvement / Feature Advisor runs.

`AdvisorStore` is the interface the rest of F2 (and integration/API code)
should depend on. `PostgresJsonbStore` is the concrete implementation used
today, storing the AdvisorReport as JSONB in the `advisor_runs` table.
Mirrors `app.cartographer.store` exactly (same interface shape, same
`get_session` usage) - see that module's docstring for the rationale.
"""

import logging
import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select

from app.advisor.model import AdvisorReport
from app.services.db import get_session
from app.services.models import AdvisorRun

logger = logging.getLogger(__name__)


class AdvisorStore(ABC):
    """Persistence interface for advisor runs.

    Implementations must be able to round-trip an AdvisorReport (plus its
    provenance - the source cartograph_run_id and/or repo_url) through
    `save` -> `get`.
    """

    @abstractmethod
    def save(
        self,
        advisor_report: AdvisorReport,
        *,
        cartograph_run_id: str | None = None,
        repo_url: str | None = None,
    ) -> str:
        """Persist a run and return its run_id (as a string)."""
        raise NotImplementedError

    @abstractmethod
    def get(self, run_id: str) -> dict | None:
        """Fetch a run by id. Returns None if it doesn't exist.

        On success returns a dict with keys: run_id, cartograph_run_id,
        repo_url, advisor_report (dict), created_at.
        """
        raise NotImplementedError


class PostgresJsonbStore(AdvisorStore):
    """Stores runs as JSONB rows in `advisor_runs`, via the existing lazy
    engine / get_session() pattern from app.services.db.
    """

    def save(
        self,
        advisor_report: AdvisorReport,
        *,
        cartograph_run_id: str | None = None,
        repo_url: str | None = None,
    ) -> str:
        row = AdvisorRun(
            cartograph_run_id=uuid.UUID(cartograph_run_id) if cartograph_run_id else None,
            repo_url=repo_url,
            advisor_report=advisor_report.model_dump(mode="json"),
        )
        with get_session() as session:
            session.add(row)
            session.flush()  # populate row.id before commit
            run_id = str(row.id)
        logger.info(
            "Saved advisor run %s (cartograph_run_id=%s, repo_url=%s)",
            run_id, cartograph_run_id, repo_url,
        )
        return run_id

    def get(self, run_id: str) -> dict | None:
        with get_session() as session:
            row = session.get(AdvisorRun, uuid.UUID(run_id))
            if row is None:
                return None
            return {
                "run_id": str(row.id),
                "cartograph_run_id": str(row.cartograph_run_id) if row.cartograph_run_id else None,
                "repo_url": row.repo_url,
                "advisor_report": row.advisor_report,
                "created_at": row.created_at.isoformat(),
            }

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Convenience helper (not part of the AdvisorStore interface) for
        listing recent runs without the full JSONB payload."""
        with get_session() as session:
            stmt = (
                select(AdvisorRun)
                .order_by(AdvisorRun.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "run_id": str(r.id),
                    "cartograph_run_id": str(r.cartograph_run_id) if r.cartograph_run_id else None,
                    "repo_url": r.repo_url,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
