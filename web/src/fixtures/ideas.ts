import type { HistoryResponse, Idea, IdeasResponse } from "../api/types";

export const sampleIdeas: Idea[] = [
  {
    pid: 1,
    name: "Changelog Synthesizer",
    problem_statement:
      "Teams ship fast but writing a readable changelog from raw commits/PR titles is a " +
      "tedious, low-priority chore that usually gets skipped.",
    why_it_fits: [
      "Plays directly to LLM strengths: summarizing noisy technical text into prose.",
      "Small, well-scoped surface area for a portfolio project.",
      "Naturally extends into a CI action or GitHub App.",
    ],
    real_world_value:
      "Saves maintainers 20-30 minutes per release and produces changelogs users " +
      "actually read, improving release communication.",
    business_value:
      "Turns release notes from a skipped chore into a reliable, on-brand artifact — " +
      "improving adoption and reducing support questions about 'what changed?'.",
    implementation_plan: [
      "Pull merged PRs/commits since the last tag via the GitHub API.",
      "Cluster changes by type (feature/fix/chore) with a lightweight classifier.",
      "Prompt an LLM to draft the changelog section in a fixed template.",
      "Ship as a CLI first, then a GitHub Action.",
    ],
    engineering_challenges: [
      "Deterministic commit → category classification that degrades gracefully on noisy messages.",
      "Idempotent generation: re-running for the same tag range must produce a stable diff.",
      "Prompt-context budgeting when a release spans hundreds of commits.",
    ],
    architectural_intent:
      "A deterministic ingestion stage (GitHub API → normalized change records) feeds a single " +
      "LLM summarization step. Keep parsing and classification out of the model so output is " +
      "reproducible and the LLM only does what it's good at: prose.",
    tradeoffs: [
      "Template-first output is consistent but less flexible than free-form generation.",
      "Rule-based pre-classification adds maintenance but keeps the LLM cheap and predictable.",
    ],
  },
  {
    pid: 2,
    name: "Dependency Drift Auditor",
    problem_statement:
      "Repos accumulate stale, vulnerable, or abandoned dependencies silently until " +
      "something breaks or a CVE lands.",
    why_it_fits: [
      "Combines static analysis with an LLM-authored human-readable risk summary.",
      "Useful against Dev-Strom's own Cartographer output — natural synergy.",
    ],
    real_world_value:
      "Turns a routine security/maintenance task into a scheduled report a team can " +
      "actually act on instead of ignoring.",
    business_value:
      "Cuts the window between a CVE landing and a team noticing, lowering breach risk " +
      "and audit friction without adding a full security hire.",
    implementation_plan: [
      "Parse manifest files (package.json, requirements.txt, pyproject.toml).",
      "Cross-reference against OSV/GitHub advisory databases.",
      "Rank by exploitability + staleness, summarize with an LLM.",
      "Output as a markdown report and a JSON feed for CI gating.",
    ],
    engineering_challenges: [
      "Reconciling version constraints across ecosystems with different resolution semantics.",
      "Scoring exploitability without drowning users in low-signal advisories.",
      "Caching advisory lookups to stay inside API rate limits at scale.",
    ],
    architectural_intent:
      "Manifest parsing and advisory cross-referencing are pure deterministic code; the LLM only " +
      "authors the human-readable risk narrative on top of an already-ranked list. Evidence " +
      "(package, version, advisory id) is attached to every finding.",
    tradeoffs: [
      "OSV/GitHub advisory coverage is broad but not exhaustive — some ecosystems lag.",
      "Static analysis can't confirm a vulnerable path is actually reachable, so severity is heuristic.",
    ],
  },
  {
    pid: 3,
    name: "Onboarding Path Generator",
    problem_statement:
      "New engineers on a codebase don't know where to start reading; READMEs go stale " +
      "and tribal knowledge lives in people's heads.",
    why_it_fits: [
      "Directly reuses a ProjectGraph-style structural model of a repo.",
      "High perceived value for relatively little scope.",
    ],
    real_world_value:
      "Cuts new-hire ramp time by giving a guided, ordered reading path through the " +
      "most load-bearing modules instead of an alphabetical file tree.",
    business_value:
      "Shortens time-to-first-commit for new engineers, reducing the hidden cost of " +
      "onboarding and the load on senior engineers who field the same questions repeatedly.",
    implementation_plan: [
      "Build a dependency graph of the repo (imports/calls).",
      "Rank modules by centrality/entrypoint proximity.",
      "Generate a narrated walkthrough ordering the top N modules.",
      "Render as an interactive doc site.",
    ],
    engineering_challenges: [
      "Graph centrality that stays meaningful across languages and monorepos.",
      "Ordering a reading path so each step only depends on concepts already introduced.",
      "Keeping the walkthrough fresh as the codebase drifts (incremental re-analysis).",
    ],
    architectural_intent:
      "Reuse a structural ProjectGraph as the source of truth; ranking is deterministic graph math, " +
      "and the LLM narrates a path over an already-computed ordering rather than 'reading' the repo. " +
      "This keeps the guided tour explainable and cheap to regenerate.",
    tradeoffs: [
      "Centrality is a proxy for importance — it can over-rank utility modules that everything imports.",
      "A precomputed path is fast but less adaptive than an interactive Q&A explorer.",
    ],
  },
];

export const sampleIdeasResponse: IdeasResponse = {
  run_id: "demo-run-ideas-0001",
  ideas: sampleIdeas,
};

export const sampleHistoryResponse: HistoryResponse = {
  runs: [
    {
      run_id: "demo-run-ideas-0001",
      tech_stack: "Python, FastAPI, React",
      domain: "developer tools",
      level: "intermediate",
      count: 3,
      created_at: "2026-08-15T14:22:00Z",
    },
    {
      run_id: "demo-run-ideas-0002",
      tech_stack: "TypeScript, Next.js",
      domain: "productivity",
      level: "beginner",
      count: 2,
      created_at: "2026-08-12T09:05:00Z",
    },
    {
      run_id: "demo-run-cartograph-0001",
      tech_stack: "Python",
      domain: undefined,
      level: undefined,
      count: 0,
      created_at: "2026-08-10T18:41:00Z",
    },
  ],
  limit: 20,
  offset: 0,
};
