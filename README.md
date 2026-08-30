# Dev-Strom

**Get concrete project ideas for any tech stack, and analyze repositories with evidence-backed findings.**

Enter a stack (e.g. LangChain, LangGraph); Dev-Strom searches the web for tutorials and articles, then uses an LLM to suggest project ideas—each with a problem statement, why it fits the stack, real-world value, and an implementation plan. Expand any idea for a detailed plan; export one as LLM-ready markdown.

**Repository Intelligence** clones and parses a repo, then returns an evidence-first analysis: findings with file/line citations, ranked recommendations, and an interactive architecture graph.

---

## Quick start

```bash
git clone <repo-url>
cd Dev-Strom
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

| Variable | Required | Description |
|---|---|---|
| `API_KEY` | Yes | LLM provider key (OpenAI-compatible, e.g. OpenRouter) |
| `TAVILY_API_KEY` | Recommended | Fallback web search when Sonar fails ([Tavily](https://tavily.com)) |
| `DATABASE_URL` | V3+ | PostgreSQL connection string (see [Database setup](#database-setup-v3)) |

---

## How to run

| Option | Command | Description |
|--------|---------|-------------|
| **Web UI** | `cd web && npm install && npm run dev` | React app on port 5173. Proxies `/api/*` to FastAPI — start the API first. |
| **API** | `uvicorn app.api:api --reload` | HTTP server on port 8000. Required for the web UI. |

`GET /health` (liveness) and `GET /ready` (readiness — pings the database when `DATABASE_URL` is configured) are available once the API is running.

> **Note:** Start the **API** and **web** dev server in separate terminals. See [web/README.md](web/README.md) for frontend details (demo mode, build, Repository Intelligence).

**Example (API):**

```bash
curl -X POST http://localhost:8000/ideas \
  -H "Content-Type: application/json" \
  -d '{"tech_stack": "React, Node.js, PostgreSQL", "domain": "fintech", "count": 2}'
```

The response includes `run_id`; use it for expand and export so concurrent clients do not overwrite each other's state.

**Expand one idea by PID (use run_id from POST /ideas; pid 1–N):**

```bash
curl -X POST http://localhost:8000/expand \
  -H "Content-Type: application/json" \
  -d '{"run_id": "<run_id from ideas response>", "pid": 1}'
```

**Export one expanded idea as markdown (call POST /expand for that pid first; use same run_id):**

```bash
curl -X POST http://localhost:8000/export \
  -H "Content-Type: application/json" \
  -d '{"run_id": "<run_id from ideas response>", "pid": 1}' \
  -o idea.md
```

**Export format (LLM-ready):** The markdown file includes (1) Context and goal (tech stack, problem, value, why-it-fits), (2) High-level implementation plan, (3) Detailed implementation plan (from expand), (4) Assumptions / Out of scope, (5) Next step (first concrete action). Designed so an LLM can execute the project from the file without hallucinating.

**Example (API with natural-language intent):**

```bash
curl -X POST http://localhost:8000/ideas \
  -H "Content-Type: application/json" \
  -d '{"intent": "Event-driven fintech backend with strong audit trails", "count": 2}'
```

**Analyze a repository (Repository Intelligence):**

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/user/repo"}'
```

Returns `run_id`, evidence-backed `findings`, `recommendations`, and a structural `graph`. List past runs with `GET /analyses`; reload one with `GET /analyze/{run_id}`. Pass `?async=true` to schedule as a background job and poll `GET /jobs/{job_id}`.

**Docs (when API is running):** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger), [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc).

---

## Architecture

### End-to-end flow (Ideas)

![Dev-Strom architecture flow](docs/architecture.png)

```
User input: intent or tech_stack
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LangGraph (app.invoke)                                                  │
│                                                                          │
│  START                                                                   │
│    │                                                                     │
│    ▼                                                                     │
│  fetch_web_context(state)                                                │
│    │  • Primary: Perplexity Sonar via OpenRouter (search_model)          │
│    │  • Fallback: Tavily (app/tools.py) if Sonar fails                   │
│    │  • Returns {"web_context": "..."}                                   │
│    ▼                                                                     │
│  generate_ideas(state)                                                   │
│    │  • Builds prompt from tech_stack/intent + web_context               │
│    │  • Invokes Deep Agent → parses JSON → ProjectIdea objects             │
│    ▼                                                                     │
│  END                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
Final state: {tech_stack, web_context, ideas}
```

**Step-by-step:**

1. **Input:** Natural-language `intent` and/or `tech_stack`, plus optional `domain`, `level`, `refinement_context`, `prior_ideas`.
2. **fetch_web_context:** Calls `fetch_real_world_problems` — Sonar first, Tavily only on failure when `TAVILY_API_KEY` is set.
3. **generate_ideas:** Deep Agent produces two grounded idea cards per run.
4. **Output:** `run_id` + ideas persisted to Postgres.

### Repository Intelligence flow

```
Git URL or local path
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  POST /analyze  (app.cartographer.pipeline)                              │
│                                                                          │
│  resolve/clone → parse → aggregate (system graph)                        │
│    │                                                                     │
│    ▼                                                                     │
│  analyze_findings (LLM, evidence-first)                                  │
│    │  • Findings with file/line/symbol citations                         │
│    │  • Recommendations ranked by impact/effort                          │
│    ▼                                                                     │
│  Persist to analysis_runs (Postgres JSONB)                               │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
Analysis + ProjectGraph  →  RepoIntelligence UI (web/)
```

### Layers

| Layer | Role |
|-------|------|
| **LangGraph** | Orchestration: `fetch_web_context` → `generate_ideas`. |
| **Sonar (OpenRouter)** | Primary live web context for idea generation (`DEVSTROM_SEARCH_MODEL`). |
| **Tavily** | Fallback web search when Sonar fails (`app/tools.py`, requires `TAVILY_API_KEY`). |
| **LangChain** | Tool wrapper for Tavily fallback. |
| **Deep Agents** | Idea generation inside the `generate_ideas` node. |
| **Cartographer package** | Internal ingest/parse/findings pipeline (`app/cartographer/`); powers `POST /analyze`. | (`schema.py`): Each idea has `name`, `problem_statement`, `why_it_fits` (list), `real_world_value`, `implementation_plan` (list of steps). 1–5 ideas per run (configurable). API returns a `run_id` (UUID) with each ideas response; use it for `POST /expand` and `POST /export` so state is per-run and safe for concurrent clients.

---

## Project layout

Application code lives under `app/` (FastAPI server, LangGraph pipeline, database
services) and `web/` (React frontend). `migrations/` holds Alembic migrations.

| Path | Purpose |
|------|---------|
| `app/graph.py` | LangGraph pipeline: state, `fetch_web_context`, `generate_ideas`, `expand_idea`, model fallback chain. |
| `app/tools.py` | Tavily web-search fallback tool (used when Sonar fails). |
| `app/services/web_context.py` | Sonar-first web context fetch for idea generation. |
| `app/api.py` | FastAPI server: ideas (`POST /ideas`, `/expand`, `/export`, `/history`), repository intelligence (`POST /analyze`, `GET /analyze/{run_id}`, `GET /analyses`), jobs (`GET /jobs/{job_id}`), health. |
| `app/cartographer/` | Internal repo-ingest pipeline: `ingest`, `parse`, `aggregate`, `findings`, `analysis_store`, `pipeline`. |
| `app/config.py` | Typed settings (`pydantic-settings`): API keys, `DATABASE_URL`, model + fallbacks, LangSmith config, log level. |
| `app/models/domain.py` | Domain models: `ProjectIdea`, `Analysis`, `Finding`, `Recommendation`, `Repository`. |
| `app/models/dto.py` | HTTP request/response DTOs for FastAPI. |
| `app/services/db.py` | Lazily-created SQLAlchemy engine, session factory, `get_session()` context manager, `ping()`. |
| `app/services/models.py` | SQLAlchemy ORM: `Run`, `ExpandedIdea`, `AnalysisRun`, `Job` (+ legacy `cartograph_runs` / `advisor_runs` tables, read-only). |
| `app/services/run_service.py` | Run/expansion persistence: `save_run`, `save_expanded_idea`, `get_latest_expansion`, `load_history`, `get_run`. |
| `app/services/export_formatter.py` | Idea + extended plan → LLM-ready Markdown for download. |
| `web/` | React + Vite frontend: Ideas, Repository Intelligence, History. See [web/README.md](web/README.md). |
| `migrations/` | Alembic migration environment and versions (`001_initial_schema.py`, ...). |
| `docs/PLAN.md` | Master architecture plan and roadmap. |
| `docs/V3_TICKETS.md` | V3 Jira-style tickets. |
| `docs/BACKLOG.md` | Deferred features (GraphRAG, auth, etc.). |

---

## Database setup (V3)

Dev-Strom V3 uses PostgreSQL with the `pgvector` extension. Run the database using Docker:

```bash
# The project uses the pgvector/pgvector:pg16 image (pgvector pre-installed)
docker run -d \
  --name devstrom-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=devstrom \
  -e POSTGRES_DB=devstrom \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

Then add to `.env`:

```
DATABASE_URL=postgresql://postgres:devstrom@localhost:5432/devstrom
```

**Verify the connection:**

```bash
source .venv/bin/activate
python -c "from app.services.db import ping; print(ping()[:60])"
# Expected: PostgreSQL 16.x (Debian...) on x86_64-pc-linux-gnu...
```

**Enable pgvector inside the database (one-time):**

```bash
docker exec -it devstrom-postgres psql -U postgres -d devstrom -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### RAG status (`web_chunks`)

The `web_chunks` table (`pgvector` embedding column, `app/services/models.py`)
and its `ivfflat` index are created by migration `001_initial_schema.py`, but
the RAG pipeline itself is **not wired up yet**: nothing writes embeddings
into `web_chunks`, and the LangGraph pipeline (`app/graph.py`) has no
retrieval node that reads from it. Web context for ideas comes from Perplexity
Sonar via OpenRouter (`app/services/web_context.py`), with Tavily as a fallback
when Sonar fails. Treat `web_chunks` as scaffolding for a future ticket, not a
working feature.

---

## Testing

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest              # unit + integration tests, coverage report printed + written to coverage.xml
ruff check .        # lint
mypy app            # type check (advisory - non-blocking in CI)
```

All tests are hermetic: the LLM (OpenAI), Tavily web search, and PostgreSQL layers are monkeypatched in
`tests/`, so the suite makes no real network or database calls and needs no API keys or running database.

CI (`.github/workflows/ci.yml`) runs `ruff check`, `mypy` (non-blocking), `pytest` with coverage, and
`pip-audit` on every push/PR - no secrets required.

## Docker

Run the API and database stack with Docker Compose:

```bash
cp .env.example .env   # fill in API_KEY / TAVILY_API_KEY
docker compose up --build
```

This starts `db` (Postgres with pgvector), a one-shot `migrate` service that runs `alembic upgrade head`
before anything else starts, and `api` (FastAPI on `:8000`). Run the React dev server separately from `web/` (`npm run dev`, port 5173).
Validate the compose file without a running daemon via `docker compose config`.

## PostgreSQL MCP (V3-6 / V3-7)

Dev-Strom uses the standalone [postgresql-mcp](https://github.com/vallaksa/postgresql-mcp) server (Docker, Streamable HTTP) so the idea agent can query past `runs` and avoid duplicate ideas.

**Prerequisites:** `postgresql-mcp` running (e.g. `curl http://127.0.0.1:3000/health`).

Add to `.env`:

```
MCP_HTTP_URL=http://127.0.0.1:3000/mcp
MCP_API_KEY=<same key as postgresql-mcp Docker>
ENABLE_MCP=true
```

With `ENABLE_MCP=false`, idea generation behaves as before (no MCP tools).

---

## License and docs

- **Plan and tickets:** [docs/PLAN.md](docs/PLAN.md), [docs/V3_TICKETS.md](docs/V3_TICKETS.md), [docs/BACKLOG.md](docs/BACKLOG.md)
