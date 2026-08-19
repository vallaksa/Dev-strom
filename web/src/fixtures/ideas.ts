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
    implementation_plan: [
      "Pull merged PRs/commits since the last tag via the GitHub API.",
      "Cluster changes by type (feature/fix/chore) with a lightweight classifier.",
      "Prompt an LLM to draft the changelog section in a fixed template.",
      "Ship as a CLI first, then a GitHub Action.",
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
    implementation_plan: [
      "Parse manifest files (package.json, requirements.txt, pyproject.toml).",
      "Cross-reference against OSV/GitHub advisory databases.",
      "Rank by exploitability + staleness, summarize with an LLM.",
      "Output as a markdown report and a JSON feed for CI gating.",
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
    implementation_plan: [
      "Build a dependency graph of the repo (imports/calls).",
      "Rank modules by centrality/entrypoint proximity.",
      "Generate a narrated walkthrough ordering the top N modules.",
      "Render as an interactive doc site.",
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
