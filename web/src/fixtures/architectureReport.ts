import type { ArchitectureReport } from "../api/types";

export const sampleArchitectureReport: ArchitectureReport = {
  summary:
    "Dev-Strom is a small, single-service FastAPI backend that pairs an LLM-driven " +
    "idea generator (LangGraph) with a Project Cartographer that ingests a repo, " +
    "parses it into a structural graph, and asks an LLM to summarize its " +
    "architecture. All persistence is a single PostgreSQL instance accessed via " +
    "JSONB-backed stores. There is no queue or worker tier yet — the cartograph " +
    "pipeline runs synchronously inline on the request.",
  components: [
    {
      name: "API Layer",
      responsibility: "FastAPI routes for ideas, expand, export, cartograph, advise, and history.",
      node_ids: ["module:app/api.py", "function:app/api.py:post_ideas", "function:app/api.py:post_cartograph"],
    },
    {
      name: "Idea Generation Pipeline",
      responsibility: "LangGraph state machine that generates and expands project ideas via an LLM.",
      node_ids: ["module:app/graph.py", "class:app/graph.py:IdeaState"],
    },
    {
      name: "Project Cartographer",
      responsibility: "Clones/ingests a repo, parses it into a ProjectGraph, and analyzes it into an ArchitectureReport.",
      node_ids: [
        "package:app.cartographer",
        "module:app/cartographer/pipeline.py",
        "module:app/cartographer/parse.py",
        "module:app/cartographer/analyze.py",
        "function:app/cartographer/pipeline.py:cartograph",
        "function:app/cartographer/analyze.py:analyze_architecture",
      ],
    },
    {
      name: "Persistence",
      responsibility: "Save/load runs, ideas, and cartograph records against PostgreSQL.",
      node_ids: [
        "package:app.services",
        "module:app/services/run_service.py",
        "module:app/services/db.py",
        "class:app/cartographer/store.py:PostgresJsonbStore",
        "service:postgresql",
      ],
    },
  ],
  layers: ["API", "Orchestration (LangGraph)", "Domain Services", "Persistence"],
  data_flow:
    "A client request hits app/api.py, which either invokes the LangGraph idea " +
    "pipeline (app/graph.py) or the Cartographer pipeline (app/cartographer/pipeline.py " +
    "-> parse.py -> analyze.py). Both paths call out to an LLM provider (OpenAI) and " +
    "persist their result through app/services/* into PostgreSQL before returning JSON " +
    "to the caller.",
  external_integrations: ["OpenAI (LLM)", "Tavily (web search)", "PostgreSQL", "GitHub (repo cloning)"],
  mermaid: `graph TD
  Client -->|HTTP| API[app/api.py]
  API --> Ideas[graph.py: idea pipeline]
  API --> Carto[cartographer/pipeline.py]
  Carto --> Parse[cartographer/parse.py]
  Carto --> Analyze[cartographer/analyze.py]
  Ideas -->|LLM calls| OpenAI[(OpenAI)]
  Analyze -->|LLM calls| OpenAI
  Ideas --> RunService[services/run_service.py]
  Carto --> Store[cartographer/store.py]
  RunService --> DB[(PostgreSQL)]
  Store --> DB`,
  risks: [
    "Cartograph runs synchronously on the request thread — large repos will block and risk request timeouts.",
    "No worker/queue tier: idea generation and repo analysis both hold an HTTP connection open for the full LLM round-trip.",
    "Single PostgreSQL instance with no visible caching layer; read-heavy history/detail views hit the DB directly.",
    "Repo cloning happens inline with no sandboxing details visible from the graph alone — worth confirming isolation for untrusted repo URLs.",
  ],
};
