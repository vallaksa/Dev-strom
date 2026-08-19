"""Pluggable persistence for Project Cartographer runs.

`CartographStore` is the interface the rest of F1 (and integration/API code)
should depend on. `PostgresJsonbStore` is the concrete implementation used
today, storing the ProjectGraph (and, once produced, the ArchitectureReport)
as JSONB in the `cartograph_runs` table. `Neo4jStore` is a deliberate stub -
it proves the interface is swappable without committing to a graph-database
dependency yet.
"""

import logging
import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select

from app.cartographer.model import ArchitectureReport, ProjectGraph
from app.services.db import get_session
from app.services.models import CartographRun

logger = logging.getLogger(__name__)


class CartographStore(ABC):
    """Persistence interface for cartograph runs.

    Implementations must be able to round-trip a ProjectGraph (and an
    optional ArchitectureReport) through `save` -> `get`.
    """

    @abstractmethod
    def save(
        self,
        project_graph: ProjectGraph,
        architecture_report: ArchitectureReport | None = None,
    ) -> str:
        """Persist a run and return its run_id (as a string)."""
        raise NotImplementedError

    @abstractmethod
    def get(self, run_id: str) -> dict | None:
        """Fetch a run by id. Returns None if it doesn't exist.

        On success returns a dict with keys: run_id, repo_url, root_path,
        project_graph (dict), architecture_report (dict | None), created_at.
        """
        raise NotImplementedError


class PostgresJsonbStore(CartographStore):
    """Stores runs as JSONB rows in `cartograph_runs`, via the existing
    lazy engine / get_session() pattern from app.services.db.
    """

    def save(
        self,
        project_graph: ProjectGraph,
        architecture_report: ArchitectureReport | None = None,
    ) -> str:
        row = CartographRun(
            repo_url=project_graph.repo_url,
            root_path=project_graph.root_path,
            project_graph=project_graph.model_dump(mode="json"),
            architecture_report=(
                architecture_report.model_dump(mode="json") if architecture_report else None
            ),
        )
        with get_session() as session:
            session.add(row)
            session.flush()  # populate row.id before commit
            run_id = str(row.id)
        logger.info("Saved cartograph run %s (repo_url=%s)", run_id, project_graph.repo_url)
        return run_id

    def get(self, run_id: str) -> dict | None:
        with get_session() as session:
            row = session.get(CartographRun, uuid.UUID(run_id))
            if row is None:
                return None
            return {
                "run_id": str(row.id),
                "repo_url": row.repo_url,
                "root_path": row.root_path,
                "project_graph": row.project_graph,
                "architecture_report": row.architecture_report,
                "created_at": row.created_at.isoformat(),
            }

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Convenience helper (not part of the CartographStore interface)
        for listing recent runs without the full JSONB payload."""
        with get_session() as session:
            stmt = (
                select(CartographRun)
                .order_by(CartographRun.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "run_id": str(r.id),
                    "repo_url": r.repo_url,
                    "root_path": r.root_path,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]


class Neo4jStore(CartographStore):
    """STUB - not implemented.

    Proves `CartographStore` is pluggable: a future graph-database-backed
    store (e.g. for native graph traversal queries) can drop in here without
    changing any caller of `CartographStore.save` / `.get`. Do not use this
    class yet; it exists only to demonstrate the interface boundary.
    """

    def __init__(self, *_args, **_kwargs):
        raise NotImplementedError(
            "Neo4jStore is a placeholder for a future graph-database-backed "
            "CartographStore implementation. Use PostgresJsonbStore for now."
        )

    def save(
        self,
        project_graph: ProjectGraph,
        architecture_report: ArchitectureReport | None = None,
    ) -> str:
        raise NotImplementedError

    def get(self, run_id: str) -> dict | None:
        raise NotImplementedError
