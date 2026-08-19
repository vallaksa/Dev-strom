import type { AdvisorReport } from "../api/types";

export const sampleAdvisorReport: AdvisorReport = {
  summary:
    "The backend is functionally solid but operationally young: synchronous LLM " +
    "and repo-analysis paths, thin test coverage around the Cartographer, and no " +
    "background job tier. The highest-leverage work is moving long-running work " +
    "off the request thread and hardening the export/history surfaces before " +
    "adding new features.",
  tech_stack: ["Python", "FastAPI", "LangGraph", "PostgreSQL", "OpenAI", "Pydantic", "SQLAlchemy"],
  quick_wins: [
    "Add a request timeout + friendly 504 around the OpenAI calls in /ideas and /advise.",
    "Cache GET /history results for a few seconds to absorb duplicate polling from the UI.",
    "Return a stable `Retry-After` header when /cartograph 503s due to missing OPENAI_API_KEY.",
  ],
  strategic_bets: [
    "Move /cartograph and /advise onto a background worker (e.g. Celery/RQ) with a polling or webhook status API.",
    "Introduce a caching/read-model layer for ProjectGraph so repeated /cartograph calls on an unchanged repo are near-instant.",
    "Add an auth layer ahead of the currently-anonymous run model so history/runs are scoped per user.",
  ],
  recommendations: [
    {
      id: "rec-001",
      category: "performance",
      title: "Move Cartograph pipeline off the request thread",
      rationale:
        "post_cartograph runs clone -> parse -> LLM-analyze synchronously inline on the HTTP " +
        "request, which risks timeouts on larger repos and ties up a worker process for the " +
        "full duration of an LLM call.",
      impact: "high",
      effort: "high",
      affected_node_ids: [
        "function:app/api.py:post_cartograph",
        "function:app/cartographer/pipeline.py:cartograph",
        "function:app/cartographer/analyze.py:analyze_architecture",
      ],
      suggested_steps: [
        "Introduce a task queue (Celery/RQ/arq) with a Postgres or Redis broker.",
        "Change POST /cartograph to enqueue and return a job id + 202 Accepted.",
        "Add GET /cartograph/{run_id}/status for polling until the record exists.",
      ],
    },
    {
      id: "rec-002",
      category: "risk",
      title: "Sandbox untrusted repo cloning",
      rationale:
        "Cartograph accepts an arbitrary repo_url; without confirmed sandboxing, cloning and " +
        "parsing untrusted repos on the API host is a supply-chain / resource-exhaustion risk.",
      impact: "high",
      effort: "medium",
      affected_node_ids: ["function:app/cartographer/pipeline.py:cartograph", "package:app.cartographer"],
      suggested_steps: [
        "Clone into an ephemeral, size- and time-limited container or temp dir with no outbound network beyond git.",
        "Enforce the existing size cap consistently across all ingestion paths (repo_url and local path).",
        "Reject symlinks and archive bombs during ingest.",
      ],
    },
    {
      id: "rec-003",
      category: "test",
      title: "Expand Cartographer test coverage for parse -> analyze",
      rationale:
        "The parse/analyze boundary is the core value of the product and the most likely place " +
        "for silent regressions when new languages or node types are added.",
      impact: "medium",
      effort: "medium",
      affected_node_ids: ["module:app/cartographer/parse.py", "module:app/cartographer/analyze.py"],
      suggested_steps: [
        "Add golden-file tests: fixture repo -> expected ProjectGraph node/edge counts.",
        "Add a contract test asserting analyze_architecture output always validates against ArchitectureReport.",
      ],
    },
    {
      id: "rec-004",
      category: "tech_debt",
      title: "Extract a shared LLM-call wrapper",
      rationale:
        "Both the idea pipeline and the Cartographer analyzer call OpenAI directly with their " +
        "own error handling; a shared wrapper would centralize retries, timeouts, and logging.",
      impact: "medium",
      effort: "low",
      affected_node_ids: ["module:app/graph.py", "module:app/cartographer/analyze.py"],
      suggested_steps: [
        "Add app/services/llm_client.py with retry/backoff and consistent error typing.",
        "Route graph.py and analyze.py through it.",
      ],
    },
    {
      id: "rec-005",
      category: "security",
      title: "Scope runs and history to an authenticated user",
      rationale:
        "All persistence currently uses an ANONYMOUS_USER_ID; history and run detail endpoints " +
        "are effectively public to anyone who can reach the API.",
      impact: "high",
      effort: "high",
      affected_node_ids: ["module:app/services/run_service.py", "service:postgresql"],
      suggested_steps: [
        "Add a lightweight auth layer (API key or session) ahead of the API layer.",
        "Add a user_id column/filter to history and run lookups.",
      ],
    },
    {
      id: "rec-006",
      category: "docs",
      title: "Document the ArchitectureReport/ProjectGraph contract",
      rationale:
        "model.py notes it's a shared contract between two collaborating agents; a short doc " +
        "would help future contributors avoid drift between the pydantic models and consumers.",
      impact: "low",
      effort: "low",
      affected_node_ids: ["package:app.cartographer"],
      suggested_steps: ["Add a CONTRACT.md next to model.py describing id conventions and required fields."],
    },
  ],
};
