"""Repository intelligence ingestion: clone/parse a repo into a ProjectGraph
and run evidence-first analysis (findings + recommendations).

Package layout:
    model.py         - pydantic contract (Node, Edge, ProjectGraph)
    ingest.py        - clone/resolve a repo URL or local path
    parse.py         - walk a local root and build a ProjectGraph
    aggregate.py     - roll file-level graph up to system-level services
    findings.py      - LLM pass producing domain Analysis objects
    analysis_store.py - persist analysis runs (Postgres JSONB)
    graph_summary.py - compact graph serialization for LLM prompts
    pipeline.py      - orchestrates ingest -> analyze_repository_with_graph
"""
