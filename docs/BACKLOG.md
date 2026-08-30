# Dev-Strom — Backlog

Features and improvements beyond the current V3 scope. Items are grouped by theme and roughly ordered by architectural impact.

---

## Sharing & History

- **Share by saved result ID** — Share a link that points to a stored run (e.g. `/result/abc123`) instead of re-running from params. Requires persistent run history (V3 covers DB storage; this adds a public-facing URL layer on top).

---

## UX & Product

- **Favorites / saved ideas** — Let users mark specific ideas as favorites and list them separately from full run history. Adds a `favorites` table (or a boolean flag on `expanded_ideas`) and a dedicated UI view. Builds on top of the V3 history page.
- **Feedback on ideas (thumbs up/down)** — Collect user ratings on generated ideas. Stored per idea per user. Can be used to fine-tune prompts, rank ideas in history, or feed into a reward model for RLHF-style prompt optimization in the future.

---

## Knowledge & RAG

- **Global knowledge base (pgvector)** — Redesign of the per-user RAG approach dropped from V3. Instead of scoping embedded web chunks per user (low hit rate — users rarely repeat the same tech stack), build a **global shared knowledge store**. All users' web search results are chunked, embedded, and stored in `web_chunks` without user scoping. Any search for "React" benefits from every past "React" search by any user. Implementation: async background embedding via `BackgroundTask` (zero user-facing latency), global retrieval at `generate_ideas` time via cosine similarity. Gated behind `ENABLE_RAG` env var.
- **Neo4j GraphRAG integration** — Replace the pgvector-based `web_chunks` table with a full Neo4j Knowledge Graph. Instead of storing raw text chunks with embeddings, use an LLM extraction step to pull entities (frameworks, features, patterns) and relationships from web search results, then store them as Nodes and Edges in Neo4j. Neo4j's native vector index replaces pgvector for similarity search, while graph traversal adds structural reasoning (e.g. "Next.js INTRODUCED Server Actions, which RUNS_ON Node.js"). This eliminates hallucinations by grounding the LLM in verified, connected data structures.
- **Pre-seeded RAG knowledge** — Run an offline script (weekly or on-demand) that uses the LLM to map out common tech stacks (React, Spring Boot, Django, etc.) into a permanent Neo4j graph. When a user asks for a known stack, the agent retrieves pre-built graph context instantly (zero Tavily latency). For novel/unknown stacks, Tavily fires dynamically, extracts entities, and permanently adds them to the graph — the system learns over time.
- **Manual knowledge base refresh** — Add a settings page action that triggers a batch update: executes a curated set of queries against Tavily, extracts entities via LLM, and refreshes the Neo4j graph with the latest data. Ensures the knowledge base stays current without waiting for user-triggered runs.

---

## Observability & Quality

- **LangSmith advanced evaluation** — Basic tracing is already live (env variables wired in V3). Next steps: build a LangSmith dataset from representative traces (good, bad, edge cases), attach online evaluators (JSON schema adherence, domain grounding), and use experiments to compare prompt/model changes side-by-side before deploying.
- **Improve markdown export check** — Strengthen validation/checks for the exported idea markdown (e.g. required sections present, non-empty critical fields, or pre-export validation of `idea` + `extended_plan`). Today export has no structure or completeness checks; low priority for backlog.

---

## Reliability & Scale

- **Async / background jobs** — Shipped for `POST /analyze` (`?async=true` + `GET /jobs/{job_id}`). A full queue/worker stack for idea generation remains backlog.
- **Queue and workers** — Decouple the FastAPI server from LangGraph execution with a task queue (Celery + Redis or similar). Required for horizontal scaling and multi-worker deployments.

---

## Auth & Security (Deferred from V3)

Full authentication stack deferred to focus on core features first. All features currently use a hardcoded anonymous user UUID. When auth is added, the anonymous UUID is swapped for the real authenticated user's UUID — zero code rewrite needed.

- **V3-4: Google OAuth2 + JWT service (backend)** — Register with Google Cloud, build the OAuth redirect flow, issue JWTs.
- **V3-5: JWT middleware + protect API routes** — FastAPI `Depends(get_current_user)` on all data routes.
- **V3-6: React login page + JWT session handling** — Auth gate in the React app (`web/`).
- **V3-7: API Key Vault — service + routes** — Encrypted storage for user-supplied OpenAI/Tavily keys using Fernet.
- **V3-8: React Settings page (key management UI)** — UI for adding/removing API keys.
- **V3-9: Wire graph + tools to use user-supplied keys** — Pull decrypted keys from DB instead of `.env` at runtime.
- **V3-16: Per-user TTL caching layer** — `cachetools.TTLCache` scoped by user ID.

---

## React Frontend

React frontend shipped as F3 (`web/`): Ideas, Repository Intelligence, History. Auth and Settings pages remain in backlog.

- **V3-17: React + Vite scaffold + routing + API client** — Done (F3).
- **V3-18: React auth (login page + JWT flow)** — Google OAuth login page consuming the backend auth routes.
- **V3-19: React Settings page** — Key management UI.

---

## V4 — Deferred from V3

Items explicitly descoped from V3 with documented rationale.

| Item | Deferred reason |
|---|---|
| Per-user RAG (pgvector) | Dropped from V3 — low hit rate (users rarely repeat same tech stack). Redesigned as global knowledge base in backlog |
| Neo4j GraphRAG | V3 ships MCP dedup instead; Neo4j rewrite is the flagship V4 feature |
| Pre-seeded RAG knowledge | Requires Neo4j infrastructure; deferred until GraphRAG is in place |
| Google OAuth + JWT auth | Overhead for current stage; all features use anonymous user until auth is implemented |
| React frontend | Shipped as F3 (`web/`); Settings/auth still backlog |
| Email + password login | Google OAuth only — password management (bcrypt, reset flow, email verification) adds complexity with no learning benefit |
| Redis caching layer | `cachetools.TTLCache` in-process is sufficient for V3; Redis needed for multi-process / distributed deployment |
| Multiple expansions history UI | Backend allows multiple expansions (no UNIQUE constraint); surfacing past expansions in the UI is a V4 UX feature |

---

*Add new items as they come up; move items into a versioned plan (e.g. V3_TICKETS, V4_TICKETS) when scheduling.*

