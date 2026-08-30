"""Roll a fine-grained ProjectGraph up to distributed-systems altitude.

Consumers (LLM analysis, React graph UI) see services, integrations, and
entrypoints — not every class/function/file. Deterministic parse still runs
internally; this module is the last step before persistence and display.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.cartographer.model import Edge, Node, ProjectGraph

# Top-level dirs we do not treat as product "services" (infra/docs only).
_SKIP_TOP_LEVEL = frozenset(
    {
        "tests",
        "test",
        "docs",
        "doc",
        "migrations",
        ".github",
        ".cursor",
        ".venv",
        "venv",
        "scripts",
        "fixtures",
        "static",
        "public",
    }
)

_DATASTORE_HINTS = (
    "postgres",
    "postgresql",
    "mysql",
    "redis",
    "neo4j",
    "mongodb",
    "mongo",
    "sqlite",
    "kafka",
    "rabbitmq",
    "elasticsearch",
    "dynamodb",
)

_INTEGRATION_HINTS = (
    "openai",
    "anthropic",
    "tavily",
    "langchain",
    "stripe",
    "aws",
    "boto",
    "google",
    "firebase",
    "supabase",
)


def _top_segment(path: str | None) -> str | None:
    if not path or path in (".", ""):
        return None
    parts = path.replace("\\", "/").strip("/").split("/")
    return parts[0] if parts else None


def _service_id(segment: str) -> str:
    return f"service:{segment}"


def _service_label(segment: str) -> str:
    labels = {
        "app": "Application API",
        "web": "Web Frontend",
        "api": "API Layer",
        "services": "Services",
        "worker": "Background Workers",
        "workers": "Background Workers",
        "frontend": "Frontend",
        "backend": "Backend",
        "mobile": "Mobile Client",
    }
    return labels.get(segment, segment.replace("-", " ").replace("_", " ").title())


def _classify_external(name: str) -> str:
    lower = name.lower()
    if any(h in lower for h in _DATASTORE_HINTS):
        return "datastore"
    if any(h in lower for h in _INTEGRATION_HINTS):
        return "integration"
    return "library"


def _is_product_path(path: str | None) -> bool:
    """True when `path` sits under a directory (not a root-level file like README.md)."""
    if not path or path in (".", ""):
        return False
    normalized = path.replace("\\", "/").strip("/")
    return "/" in normalized


def to_system_graph(full: ProjectGraph) -> ProjectGraph:
    """Return a small system-level graph derived from `full`."""
    nodes_by_id = {n.id: n for n in full.nodes}
    repo_nodes = [n for n in full.nodes if n.type == "repo"]
    repo_id = repo_nodes[0].id if repo_nodes else "repo:repo"

    # Map every structural node path → top-level service segment.
    path_to_service: dict[str, str] = {}
    for n in full.nodes:
        if n.type in ("class", "function"):
            continue
        if n.type == "file" and not _is_product_path(n.path):
            continue
        seg = _top_segment(n.path)
        if seg and seg not in _SKIP_TOP_LEVEL and _is_product_path(n.path):
            path_to_service[n.path or ""] = seg
        elif n.type == "package" and n.path and _is_product_path(n.path):
            seg = _top_segment(n.path)
            if seg and seg not in _SKIP_TOP_LEVEL:
                path_to_service[n.path] = seg

    service_segments = sorted(set(path_to_service.values()))
    if not service_segments:
        service_segments = ["core"]
        path_to_service["."] = "core"

    out_nodes: dict[str, Node] = {}
    for rn in repo_nodes:
        out_nodes[rn.id] = rn.model_copy(
            update={"summary": "Repository root — system view (services & integrations only)."}
        )

    module_counts: dict[str, int] = defaultdict(int)
    for n in full.nodes:
        if n.type != "module":
            continue
        seg = _top_segment(n.path)
        if seg:
            module_counts[seg] += 1

    for seg in service_segments:
        sid = _service_id(seg)
        count = module_counts.get(seg, 0)
        out_nodes[sid] = Node(
            id=sid,
            type="service",
            label=_service_label(seg),
            path=seg,
            summary=f"Bounded context under `{seg}/` ({count} Python modules detected).",
            meta={"module_count": count, "scope": seg},
        )

    for n in full.nodes:
        if n.type != "external_dep":
            continue
        kind = _classify_external(n.label)
        out_nodes[n.id] = n.model_copy(
            update={
                "summary": f"{kind.replace('_', ' ').title()}: {n.label}",
                "meta": {**n.meta, "integration_kind": kind},
            }
        )

    # Entrypoints → entrypoint nodes tied to a service.
    entrypoint_nodes: list[Node] = []
    for ep in full.entrypoints:
        ep_node = nodes_by_id.get(ep)
        ep_path = ep_node.path if ep_node else ep.replace("module:", "").replace("file:", "")
        seg = _top_segment(ep_path) or service_segments[0]
        if seg in _SKIP_TOP_LEVEL or seg not in service_segments:
            seg = service_segments[0]
        ep_id = f"entrypoint:{ep}"
        label = ep_path.split("/")[-1] if ep_path else "entry"
        entrypoint_nodes.append(
            Node(
                id=ep_id,
                type="entrypoint",
                label=label,
                path=ep_path,
                summary=f"Runtime entry under `{seg}/`.",
                meta={"service": seg, "source_node": ep},
            )
        )
        out_nodes[ep_id] = entrypoint_nodes[-1]

    # Aggregate edges: service ↔ service, service → external, repo → service.
    edge_keys: set[tuple[str, str, str]] = set()
    out_edges: list[Edge] = []

    def add_edge(source: str, target: str, etype: str, meta: dict | None = None) -> None:
        key = (source, target, etype)
        if key in edge_keys or source == target:
            return
        edge_keys.add(key)
        out_edges.append(Edge(source=source, target=target, type=etype, meta=meta or {}))

    for seg in service_segments:
        add_edge(repo_id, _service_id(seg), "contains")

    for ep_n in entrypoint_nodes:
        seg = ep_n.meta.get("service", service_segments[0])
        add_edge(_service_id(str(seg)), ep_n.id, "exposes")

    for e in full.edges:
        if e.type not in ("imports", "depends_on", "calls"):
            continue
        src = nodes_by_id.get(e.source)
        tgt = nodes_by_id.get(e.target)
        if tgt and tgt.type == "external_dep":
            src_seg = _top_segment(src.path if src else None) or (
                _top_segment(e.source.replace("module:", "").replace("file:", ""))
            )
            if src_seg and src_seg in service_segments:
                add_edge(_service_id(src_seg), tgt.id, "depends_on", meta={"aggregated": True})
            else:
                add_edge(repo_id, tgt.id, "depends_on", meta={"aggregated": True})
            continue
        if not src or not tgt:
            continue
        if src.type in ("class", "function") or tgt.type in ("class", "function"):
            continue
        src_seg = _top_segment(src.path)
        tgt_seg = _top_segment(tgt.path)
        if not src_seg or not tgt_seg or src_seg == tgt_seg:
            continue
        if src_seg in service_segments and tgt_seg in service_segments:
            add_edge(_service_id(src_seg), _service_id(tgt_seg), "imports", meta={"aggregated": True})

    patterns = _infer_patterns(service_segments, out_nodes, out_edges, full)
    stats = dict(full.stats or {})
    stats["granularity"] = "system"
    stats["full_node_count"] = len(full.nodes)
    stats["full_edge_count"] = len(full.edges)
    stats["architecture_patterns"] = patterns
    stats["nodes_by_type"] = {}
    for n in out_nodes.values():
        stats["nodes_by_type"][n.type] = stats["nodes_by_type"].get(n.type, 0) + 1

    return ProjectGraph(
        repo_url=full.repo_url,
        root_path=full.root_path,
        languages=full.languages,
        nodes=list(out_nodes.values()),
        edges=out_edges,
        entrypoints=[n.id for n in entrypoint_nodes],
        manifests=full.manifests,
        stats=stats,
    )


def _infer_patterns(
    services: list[str],
    nodes: dict[str, Node],
    edges: list[Edge],
    full: ProjectGraph,
) -> list[str]:
    patterns: list[str] = []
    has_web = "web" in services or "frontend" in services
    has_api = "app" in services or "api" in services or "backend" in services
    if has_web and has_api:
        patterns.append("BFF / split frontend & backend")
    if len(services) == 1:
        patterns.append("Modular monolith")
    elif len(services) >= 3:
        patterns.append("Multi-service / modular boundaries")

    ext_kinds = {
        n.meta.get("integration_kind")
        for n in nodes.values()
        if n.type == "external_dep"
    }
    if "datastore" in ext_kinds:
        patterns.append("Persistent datastore integration")
    if "integration" in ext_kinds:
        patterns.append("External SaaS / LLM integration")

    manifests = full.manifests or {}
    has_dockerfile = any(
        n.type == "file" and "dockerfile" in (n.label or n.path or "").lower()
        for n in full.nodes
    )
    if has_dockerfile:
        patterns.append("Container-oriented deployment")

    if re.search(r"fastapi|uvicorn|flask|django", str(manifests).lower()):
        patterns.append("HTTP API server")
    if re.search(r"react|vite|next", str(manifests).lower()) or has_web:
        patterns.append("SPA / component UI")

    return patterns[:8]
