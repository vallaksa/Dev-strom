"""Project Cartographer (F1): repo ingestion, structural parsing, and a
normalized ProjectGraph contract shared with the LLM-analyzer/API agent.

Package layout:
    model.py    - pydantic contract (Node, Edge, ProjectGraph, ArchitectureReport)
    ingest.py   - clone/resolve a repo URL or local path to a local root path
    parse.py    - walk a local root path and build a ProjectGraph
    store.py    - pluggable persistence (PostgresJsonbStore now, Neo4jStore later)
    pipeline.py - orchestrates ingest -> parse into a single entry point
"""
