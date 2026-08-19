"""Pluggable persistence for Project Cartographer runs.

`CartographStore` is the interface the rest of F1 (and integration/API code)
should depend on. `PostgresJsonbStore` is the concrete implementation used
today, storing the ProjectGraph (and, once produced, the ArchitectureReport)
as JSONB in the `cartograph_runs` table. `Neo4jStore` is a graph-database-
backed implementation that models ProjectGraph nodes/edges as native Neo4j
nodes/relationships, enabling Cypher graph traversal instead of JSONB blob
inspection.
"""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import get_args

import neo4j
from sqlalchemy import select

from app.cartographer.model import ArchitectureReport, EdgeType, ProjectGraph
from app.config import settings
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


_VALID_EDGE_TYPES = frozenset(get_args(EdgeType))


class Neo4jStore(CartographStore):
    """Stores runs as a native graph in Neo4j.

    Each ProjectGraph becomes a `:CartographRun` node with `:HAS_NODE`
    relationships to one `:GraphNode` per `Node`, and `Edge`s become
    relationships (dynamically typed by `edge.type`) directly between the
    corresponding `:GraphNode`s - enabling native Cypher graph traversal,
    unlike `PostgresJsonbStore`'s opaque JSONB blob.

    `Node.id` (e.g. "module:app/api.py") is only unique *within* a single
    ProjectGraph, so it is not used as the Neo4j merge key directly (it would
    collide across different repos/runs). Instead every `:GraphNode` is keyed
    on a run-scoped `run_key` (`f"{run_id}:{node.id}"`); the original id is
    kept as the `orig_id` property.

    Mirrors the lazy-connection idiom of `app.services.db`: the driver is
    created lazily on first use, never at import or `__init__` time, so
    `import app` never crashes just because Neo4j isn't configured/running.
    `save()` / `get()` raise a clear RuntimeError if NEO4J_URI was never
    configured.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self._uri = uri if uri is not None else settings.neo4j_uri
        self._user = user if user is not None else settings.neo4j_user
        self._password = password if password is not None else settings.neo4j_password
        self._driver: neo4j.Driver | None = None

    def _get_driver(self) -> neo4j.Driver:
        if self._driver is None:
            if not self._uri:
                raise RuntimeError(
                    "NEO4J_URI is not set. Configure NEO4J_URI (and optionally "
                    "NEO4J_USER / NEO4J_PASSWORD) in .env to use the Neo4j-backed "
                    "CartographStore."
                )
            auth = (self._user, self._password) if self._user else None
            self._driver = neo4j.GraphDatabase.driver(self._uri, auth=auth)
        return self._driver

    def close(self) -> None:
        """Release the underlying driver, if one was ever created."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def save(
        self,
        project_graph: ProjectGraph,
        architecture_report: ArchitectureReport | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        with self._get_driver().session() as session:
            session.run(
                """
                CREATE (r:CartographRun {
                    id: $id,
                    repo_url: $repo_url,
                    root_path: $root_path,
                    languages: $languages,
                    entrypoints: $entrypoints,
                    manifests: $manifests,
                    stats: $stats,
                    architecture_report: $architecture_report,
                    created_at: $created_at
                })
                """,
                id=run_id,
                repo_url=project_graph.repo_url,
                root_path=project_graph.root_path,
                languages=list(project_graph.languages),
                entrypoints=list(project_graph.entrypoints),
                manifests=json.dumps(project_graph.manifests),
                stats=json.dumps(project_graph.stats),
                architecture_report=(
                    json.dumps(architecture_report.model_dump(mode="json"))
                    if architecture_report is not None
                    else None
                ),
                created_at=created_at,
            )

            for node in project_graph.nodes:
                run_key = f"{run_id}:{node.id}"
                session.run(
                    """
                    MATCH (r:CartographRun {id: $run_id})
                    MERGE (n:GraphNode {run_key: $run_key})
                    SET n.orig_id = $orig_id,
                        n.type = $type,
                        n.label = $label,
                        n.path = $path,
                        n.language = $language,
                        n.summary = $summary,
                        n.meta = $meta
                    MERGE (r)-[:HAS_NODE]->(n)
                    """,
                    run_id=run_id,
                    run_key=run_key,
                    orig_id=node.id,
                    type=node.type,
                    label=node.label,
                    path=node.path,
                    language=node.language,
                    summary=node.summary,
                    meta=json.dumps(node.meta),
                )

            for edge in project_graph.edges:
                if edge.type not in _VALID_EDGE_TYPES:
                    # Guards against Cypher injection via the interpolated
                    # relationship type below - only known EdgeType literals
                    # from app.cartographer.model are ever allowed through.
                    raise ValueError(
                        f"Unknown edge type {edge.type!r}; expected one of {sorted(_VALID_EDGE_TYPES)}."
                    )
                source_key = f"{run_id}:{edge.source}"
                target_key = f"{run_id}:{edge.target}"
                # Cypher relationship types must be identifiers, not query
                # parameters - safe to interpolate here only because edge.type
                # was just validated against the closed EdgeType literal set.
                cypher = (
                    "MATCH (a:GraphNode {run_key: $source_key}), (b:GraphNode {run_key: $target_key}) "
                    f"CREATE (a)-[rel:`{edge.type}` {{meta: $meta}}]->(b)"
                )
                session.run(
                    cypher,
                    source_key=source_key,
                    target_key=target_key,
                    meta=json.dumps(edge.meta),
                )

        logger.info("Saved cartograph run %s to Neo4j (repo_url=%s)", run_id, project_graph.repo_url)
        return run_id

    def get(self, run_id: str) -> dict | None:
        with self._get_driver().session() as session:
            run_record = session.run(
                "MATCH (r:CartographRun {id: $run_id}) RETURN r LIMIT 1",
                run_id=run_id,
            ).single()
            if run_record is None:
                return None
            r = run_record["r"]

            nodes = []
            node_records = session.run(
                "MATCH (:CartographRun {id: $run_id})-[:HAS_NODE]->(n:GraphNode) RETURN n",
                run_id=run_id,
            )
            for rec in node_records:
                n = rec["n"]
                meta_raw = n.get("meta")
                nodes.append(
                    {
                        "id": n.get("orig_id"),
                        "type": n.get("type"),
                        "label": n.get("label"),
                        "path": n.get("path"),
                        "language": n.get("language"),
                        "summary": n.get("summary"),
                        "meta": json.loads(meta_raw) if meta_raw else {},
                    }
                )

            edges = []
            edge_records = session.run(
                "MATCH (a:GraphNode)-[rel]->(b:GraphNode) "
                "WHERE a.run_key STARTS WITH $prefix AND b.run_key STARTS WITH $prefix "
                "RETURN a.orig_id AS source, type(rel) AS rel_type, b.orig_id AS target, "
                "rel.meta AS meta",
                prefix=f"{run_id}:",
            )
            for rec in edge_records:
                meta_raw = rec["meta"]
                edges.append(
                    {
                        "source": rec["source"],
                        "target": rec["target"],
                        "type": rec["rel_type"],
                        "meta": json.loads(meta_raw) if meta_raw else {},
                    }
                )

            architecture_report = None
            ar_raw = r.get("architecture_report")
            if ar_raw:
                architecture_report = json.loads(ar_raw)

            project_graph = {
                "repo_url": r.get("repo_url"),
                "root_path": r.get("root_path"),
                "languages": list(r.get("languages") or []),
                "nodes": nodes,
                "edges": edges,
                "entrypoints": list(r.get("entrypoints") or []),
                "manifests": json.loads(r["manifests"]) if r.get("manifests") else {},
                "stats": json.loads(r["stats"]) if r.get("stats") else {},
            }

            return {
                "run_id": r.get("id"),
                "repo_url": r.get("repo_url"),
                "root_path": r.get("root_path"),
                "project_graph": project_graph,
                "architecture_report": architecture_report,
                "created_at": r.get("created_at"),
            }


def get_cartograph_store() -> CartographStore:
    """Return the configured `CartographStore` implementation.

    Selected via `CARTOGRAPH_STORE_BACKEND` (app.config.settings):
    "postgres" (default) -> `PostgresJsonbStore`, "neo4j" -> `Neo4jStore`.
    This is the single integration seam callers (e.g. app/api.py) need to
    swap backends without branching on config themselves.
    """
    backend = (settings.cartograph_store_backend or "postgres").strip().lower()
    if backend == "neo4j":
        return Neo4jStore()
    if backend == "postgres":
        return PostgresJsonbStore()
    raise ValueError(f"Unknown CARTOGRAPH_STORE_BACKEND={backend!r}; expected 'postgres' or 'neo4j'.")
