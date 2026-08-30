import type { ProjectGraph } from "../api/types";

/**
 * Demo-mode ProjectGraph modeled on Dev-Strom's backend. Used when demo mode
 * is on so the Repository Intelligence architecture tab has a rich graph.
 */
export const sampleProjectGraph: ProjectGraph = {
  repo_url: "https://github.com/example-org/dev-strom",
  root_path: "/repo/dev-strom",
  languages: ["python", "sql"],
  entrypoints: ["entrypoint:uvicorn-app.api:api"],
  manifests: {
    "pyproject.toml": { name: "dev-strom", python: ">=3.11" },
    "requirements.txt": { lines: 18 },
  },
  stats: {
    node_count: 20,
    edge_count: 24,
    file_count: 11,
    loc_estimate: 3400,
  },
  nodes: [
    { id: "repo:dev-strom", type: "repo", label: "dev-strom", path: ".", language: undefined, summary: "Idea generator + repository intelligence for developer projects.", meta: {} },

    { id: "package:app", type: "package", label: "app", path: "app/", language: "python", summary: "FastAPI application package.", meta: {} },
    { id: "package:app.cartographer", type: "package", label: "app.cartographer", path: "app/cartographer/", language: "python", summary: "Repo ingestion, parsing, and evidence-first analysis.", meta: {} },
    { id: "package:app.services", type: "package", label: "app.services", path: "app/services/", language: "python", summary: "Persistence and formatting services.", meta: {} },

    { id: "module:app/api.py", type: "module", label: "api.py", path: "app/api.py", language: "python", summary: "FastAPI routes: /ideas, /analyze, /analyses, /history.", meta: {} },
    { id: "module:app/graph.py", type: "module", label: "graph.py", path: "app/graph.py", language: "python", summary: "LangGraph idea-generation and expansion pipeline.", meta: {} },
    { id: "module:app/config.py", type: "module", label: "config.py", path: "app/config.py", language: "python", summary: "Typed settings loaded from environment.", meta: {} },
    { id: "module:app/cartographer/pipeline.py", type: "module", label: "pipeline.py", path: "app/cartographer/pipeline.py", language: "python", summary: "Clone/ingest a repo and run evidence-first analysis.", meta: {} },
    { id: "module:app/cartographer/findings.py", type: "module", label: "findings.py", path: "app/cartographer/findings.py", language: "python", summary: "LLM pass producing findings and recommendations.", meta: {} },
    { id: "module:app/cartographer/parse.py", type: "module", label: "parse.py", path: "app/cartographer/parse.py", language: "python", summary: "AST-based parser building nodes/edges.", meta: {} },
    { id: "module:app/services/run_service.py", type: "module", label: "run_service.py", path: "app/services/run_service.py", language: "python", summary: "Save/load idea-generation runs.", meta: {} },
    { id: "module:app/services/db.py", type: "module", label: "db.py", path: "app/services/db.py", language: "python", summary: "SQLAlchemy engine + connection helpers.", meta: {} },

    { id: "class:app/cartographer/analysis_store.py:PostgresJsonbStore", type: "class", label: "PostgresJsonbStore", path: "app/cartographer/analysis_store.py", language: "python", summary: "Persists Analysis + ProjectGraph as JSONB rows.", meta: {} },
    { id: "class:app/graph.py:IdeaState", type: "class", label: "IdeaState", path: "app/graph.py", language: "python", summary: "Typed state threaded through the LangGraph pipeline.", meta: {} },

    { id: "function:app/api.py:post_ideas", type: "function", label: "post_ideas()", path: "app/api.py", language: "python", summary: "POST /ideas handler.", meta: {} },
    { id: "function:app/api.py:post_analyze", type: "function", label: "post_analyze()", path: "app/api.py", language: "python", summary: "POST /analyze handler.", meta: {} },
    { id: "function:app/cartographer/pipeline.py:analyze_repository_with_graph", type: "function", label: "analyze_repository_with_graph()", path: "app/cartographer/pipeline.py", language: "python", summary: "Orchestrates ingest -> parse -> Analysis + graph.", meta: {} },
    { id: "function:app/cartographer/findings.py:analyze_findings", type: "function", label: "analyze_findings()", path: "app/cartographer/findings.py", language: "python", summary: "Evidence-first LLM analysis over a ProjectGraph.", meta: {} },

    { id: "ext:fastapi", type: "external_dep", label: "fastapi", language: "python", summary: "Web framework.", meta: { version: "^0.115" } },
    { id: "ext:openai", type: "external_dep", label: "openai", language: "python", summary: "LLM provider SDK.", meta: { version: "^1.50" } },
    { id: "ext:langgraph", type: "external_dep", label: "langgraph", language: "python", summary: "Graph-based LLM orchestration.", meta: { version: "^0.2" } },

    { id: "service:postgresql", type: "service", label: "PostgreSQL", summary: "Primary datastore for runs, ideas, and analysis records.", meta: { managed: true } },

    { id: "entrypoint:uvicorn-app.api:api", type: "entrypoint", label: "uvicorn app.api:api", summary: "ASGI process entrypoint.", meta: { port: 8000 } },

    { id: "file:requirements.txt", type: "file", label: "requirements.txt", path: "requirements.txt", summary: "Pinned production dependencies.", meta: {} },
  ],
  edges: [
    { source: "repo:dev-strom", target: "package:app", type: "contains", meta: {} },
    { source: "repo:dev-strom", target: "file:requirements.txt", type: "contains", meta: {} },
    { source: "package:app", target: "package:app.cartographer", type: "contains", meta: {} },
    { source: "package:app", target: "package:app.services", type: "contains", meta: {} },
    { source: "package:app", target: "module:app/api.py", type: "contains", meta: {} },
    { source: "package:app", target: "module:app/graph.py", type: "contains", meta: {} },
    { source: "package:app", target: "module:app/config.py", type: "contains", meta: {} },
    { source: "package:app.cartographer", target: "module:app/cartographer/pipeline.py", type: "contains", meta: {} },
    { source: "package:app.cartographer", target: "module:app/cartographer/findings.py", type: "contains", meta: {} },
    { source: "package:app.cartographer", target: "module:app/cartographer/parse.py", type: "contains", meta: {} },
    { source: "package:app.services", target: "module:app/services/run_service.py", type: "contains", meta: {} },
    { source: "package:app.services", target: "module:app/services/db.py", type: "contains", meta: {} },

    { source: "module:app/api.py", target: "function:app/api.py:post_ideas", type: "contains", meta: {} },
    { source: "module:app/api.py", target: "function:app/api.py:post_analyze", type: "contains", meta: {} },
    { source: "module:app/cartographer/pipeline.py", target: "function:app/cartographer/pipeline.py:analyze_repository_with_graph", type: "contains", meta: {} },
    { source: "module:app/cartographer/findings.py", target: "function:app/cartographer/findings.py:analyze_findings", type: "contains", meta: {} },
    { source: "module:app/graph.py", target: "class:app/graph.py:IdeaState", type: "contains", meta: {} },

    { source: "module:app/api.py", target: "module:app/graph.py", type: "imports", meta: {} },
    { source: "module:app/api.py", target: "module:app/config.py", type: "imports", meta: {} },
    { source: "module:app/api.py", target: "module:app/cartographer/pipeline.py", type: "imports", meta: {} },
    { source: "module:app/api.py", target: "module:app/services/run_service.py", type: "imports", meta: {} },
    { source: "module:app/cartographer/pipeline.py", target: "module:app/cartographer/parse.py", type: "imports", meta: {} },
    { source: "module:app/cartographer/pipeline.py", target: "module:app/cartographer/findings.py", type: "imports", meta: {} },
    { source: "module:app/services/run_service.py", target: "module:app/services/db.py", type: "imports", meta: {} },
    { source: "module:app/graph.py", target: "ext:langgraph", type: "imports", meta: {} },
    { source: "module:app/graph.py", target: "ext:openai", type: "imports", meta: {} },
    { source: "module:app/api.py", target: "ext:fastapi", type: "imports", meta: {} },

    { source: "function:app/api.py:post_analyze", target: "function:app/cartographer/pipeline.py:analyze_repository_with_graph", type: "calls", meta: {} },
    { source: "function:app/cartographer/pipeline.py:analyze_repository_with_graph", target: "function:app/cartographer/findings.py:analyze_findings", type: "calls", meta: {} },
    { source: "function:app/api.py:post_ideas", target: "class:app/graph.py:IdeaState", type: "calls", meta: {} },

    { source: "package:app.cartographer", target: "ext:openai", type: "depends_on", meta: {} },
    { source: "package:app", target: "ext:fastapi", type: "depends_on", meta: {} },
    { source: "module:app/services/db.py", target: "service:postgresql", type: "depends_on", meta: {} },

    { source: "class:app/cartographer/analysis_store.py:PostgresJsonbStore", target: "service:postgresql", type: "reads_writes", meta: {} },
    { source: "module:app/services/run_service.py", target: "service:postgresql", type: "reads_writes", meta: {} },

    { source: "entrypoint:uvicorn-app.api:api", target: "module:app/api.py", type: "exposes", meta: {} },
  ],
};
