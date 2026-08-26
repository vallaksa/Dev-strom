import type { Analysis } from "../api/types";
import { sampleProjectGraph } from "./projectGraph";

/**
 * Demo-mode Analysis — a realistic evidence-first analysis of the Dev-Strom
 * backend itself, exercising every field the Repository Intelligence view
 * renders (repository metadata, findings with located evidence + confidence,
 * and impact/priority-ranked recommendations linked back to findings).
 */
export const sampleAnalysis: Analysis = {
  run_id: "demo-analysis-run-0001",
  id: "demo-analysis-0001",
  status: "complete",
  created_at: "2026-08-20T15:12:00Z",
  summary:
    "Dev-Strom is a single-service FastAPI backend that pairs an LLM idea generator " +
    "(LangGraph) with a repository-analysis engine. Deterministic ingestion parses a repo " +
    "into structured metadata and a dependency model; LLM reasoning then produces evidence-" +
    "backed findings and ranked recommendations on top of that model. Persistence is a single " +
    "PostgreSQL instance (JSONB), with Neo4j available as an opt-in graph store. Analysis " +
    "currently runs inline on the request thread — the largest structural constraint.",
  repository: {
    id: "repo-demo-0001",
    url: "https://github.com/example-org/dev-strom",
    root_path: "/repos/dev-strom",
    commit_sha: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    language: "Python",
    languages: ["Python", "TypeScript", "CSS"],
    dependencies: [
      { name: "fastapi", ecosystem: "pypi", source: "pyproject.toml", version: "0.115.0" },
      { name: "langgraph", ecosystem: "pypi", source: "pyproject.toml", version: "0.2.28" },
      { name: "sqlalchemy", ecosystem: "pypi", source: "pyproject.toml", version: "2.0.35" },
      { name: "pydantic", ecosystem: "pypi", source: "pyproject.toml", version: "2.9.2" },
      { name: "neo4j", ecosystem: "pypi", source: "pyproject.toml", version: "5.24.0" },
      { name: "react", ecosystem: "npm", source: "web/package.json", version: "19.2.8" },
      { name: "@xyflow/react", ecosystem: "npm", source: "web/package.json", version: "12.11.3" },
      { name: "vite", ecosystem: "npm", source: "web/package.json", version: "6.4.3" },
    ],
    entrypoints: ["app/api.py", "app/graph.py", "web/src/main.tsx"],
    file_count: 148,
    loc: 11420,
    created_at: "2026-08-20T15:11:40Z",
  },
  findings: [
    {
      id: "finding-1",
      repository_id: "repo-demo-0001",
      category: "architecture",
      title: "Deterministic ingestion is cleanly separated from LLM reasoning",
      description:
        "Repository ingestion (clone, file discovery, language detection, dependency extraction) is " +
        "implemented as ordinary code and produces a structured model before any LLM is invoked. The " +
        "analyzer reasons over that model rather than raw files, keeping structural output reproducible.",
      confidence: 0.92,
      severity: "info",
      evidence: [
        {
          file: "app/cartographer/pipeline.py",
          line_start: 34,
          line_end: 58,
          symbol: "cartograph",
          snippet: "graph = parse_repository(root)\nreport = analyze_architecture(graph)",
          explanation:
            "parse_repository() is pure code; only analyze_architecture() calls the LLM, and it consumes the " +
            "already-built graph — a clean deterministic/reasoning split.",
        },
      ],
    },
    {
      id: "finding-2",
      repository_id: "repo-demo-0001",
      category: "scalability",
      title: "Analysis runs synchronously on the request thread",
      description:
        "POST /cartograph and /analyze perform clone → parse → LLM inline and return on the same request. " +
        "Large repositories will block a worker for the full LLM round-trip and risk request timeouts.",
      confidence: 0.86,
      severity: "high",
      evidence: [
        {
          file: "app/api.py",
          line_start: 112,
          line_end: 126,
          symbol: "post_cartograph",
          snippet: "result = cartograph(req.repo_url or req.path)\nreturn CartographResponse(...)",
          explanation:
            "The handler awaits the full pipeline before responding; there is no job/worker hand-off on the " +
            "default (non-async) path.",
        },
      ],
    },
    {
      id: "finding-3",
      repository_id: "repo-demo-0001",
      category: "security",
      title: "Untrusted repositories are cloned without visible sandboxing",
      description:
        "The analyzer accepts an arbitrary repo_url and clones it on the API host. Without confirmed " +
        "isolation, cloning and parsing untrusted repos is a supply-chain and resource-exhaustion risk.",
      confidence: 0.71,
      severity: "critical",
      evidence: [
        {
          file: "app/cartographer/ingest.py",
          line_start: 21,
          line_end: 40,
          symbol: "clone_repo",
          snippet: 'subprocess.run(["git", "clone", "--depth", "1", url, dest])',
          explanation:
            "The clone runs on the host with no container boundary or outbound-network restriction visible in " +
            "the ingestion path.",
        },
      ],
    },
    {
      id: "finding-4",
      repository_id: "repo-demo-0001",
      category: "maintainability",
      title: "LLM calls are duplicated across the idea and analysis paths",
      description:
        "The idea pipeline and the repository analyzer each call the LLM provider directly with their own " +
        "ad-hoc error handling, so retries, timeouts, and logging are not applied consistently.",
      confidence: 0.8,
      severity: "medium",
      evidence: [
        {
          file: "app/graph.py",
          line_start: 88,
          line_end: 96,
          symbol: "generate_ideas",
          snippet: "resp = client.chat.completions.create(...)",
          explanation: "A raw provider call with local try/except.",
        },
        {
          file: "app/cartographer/analyze.py",
          line_start: 60,
          line_end: 71,
          symbol: "analyze_architecture",
          snippet: "resp = client.chat.completions.create(...)",
          explanation: "A second, near-identical raw call — no shared wrapper.",
        },
      ],
    },
    {
      id: "finding-5",
      repository_id: "repo-demo-0001",
      category: "testing",
      title: "The parse → analyze boundary is thinly covered",
      description:
        "Parsing and analysis are the core value of the product and the most likely place for silent " +
        "regressions as new languages or node types are added, yet contract tests around them are sparse.",
      confidence: 0.68,
      severity: "medium",
      evidence: [
        {
          file: "tests/unit/test_parse.py",
          line_start: null,
          line_end: null,
          symbol: null,
          snippet: null,
          explanation:
            "Only happy-path parsing is asserted; there is no contract test that analyze_architecture output " +
            "always validates against the ArchitectureReport schema.",
        },
      ],
    },
  ],
  recommendations: [
    {
      id: "rec-1",
      finding_id: "finding-3",
      type: "security",
      title: "Sandbox untrusted repository cloning",
      description:
        "Clone into an ephemeral, size- and time-limited container with no outbound network beyond git, " +
        "and reject symlinks and archive bombs during ingest.",
      impact: "high",
      effort: "medium",
      priority: 1,
    },
    {
      id: "rec-2",
      finding_id: "finding-2",
      type: "scalability",
      title: "Move analysis onto a background worker",
      description:
        "Change POST /analyze to enqueue a job and return 202 + job id; poll GET /jobs/{id} until the " +
        "Analysis exists. This frees the request pool and removes the timeout ceiling on large repos.",
      impact: "high",
      effort: "high",
      priority: 2,
    },
    {
      id: "rec-3",
      finding_id: "finding-4",
      type: "engineering",
      title: "Extract a shared LLM-call wrapper",
      description:
        "Route both the idea pipeline and the analyzer through one app/services/llm_client.py with " +
        "centralized retry/backoff, timeouts, and structured logging.",
      impact: "medium",
      effort: "low",
      priority: 3,
    },
    {
      id: "rec-4",
      finding_id: "finding-5",
      type: "developer_experience",
      title: "Add golden-file + contract tests for parse → analyze",
      description:
        "Assert fixture-repo → expected node/edge counts, and that analyze output always validates against " +
        "the report schema, so structural regressions fail loudly in CI.",
      impact: "medium",
      effort: "medium",
      priority: 4,
    },
    {
      id: "rec-5",
      finding_id: null,
      type: "product",
      title: "Surface analysis evidence in the export",
      description:
        "Include the file/line/symbol citations behind each finding in the Markdown export so a reader can " +
        "trace every conclusion back to the code without re-running analysis.",
      impact: "low",
      effort: "low",
      priority: 5,
    },
  ],
  // Structural graph (file/module/class level) is built deterministically
  // during ingestion; mermaid is a curated component-level flowchart from the
  // analysis LLM call. Both render on the Architecture tab at different
  // altitudes. Either may be null in a real run — the UI falls back.
  graph: sampleProjectGraph,
  mermaid: `flowchart TD
  Web[React UI] -->|HTTP| API[FastAPI · app/api.py]
  API --> Ideas[Idea Pipeline · LangGraph]
  API --> Analyze[Repository Analysis]
  Analyze --> Ingest[Deterministic Ingestion]
  Analyze --> Reason[LLM Reasoning]
  Ideas -->|LLM| OpenAI[(OpenAI)]
  Reason -->|LLM| OpenAI
  API --> Store[Services Layer]
  Store --> PG[(PostgreSQL)]
  Store -.opt-in.-> Neo[(Neo4j)]`,
};
