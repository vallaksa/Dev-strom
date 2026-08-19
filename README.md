# Dev-Strom

**Get 1–5 concrete project ideas for any tech stack.** Enter a stack (e.g. LangChain, LangGraph); Dev-Strom searches the web for tutorials and articles, then uses an LLM to suggest project ideas—each with a problem statement, why it fits the stack, real-world value, and an implementation plan. Expand any idea for a detailed plan; export one as LLM-ready markdown.

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
| `OPENAI_API_KEY` | Yes | For the idea-generation agent ([OpenAI](https://platform.openai.com/api-keys)) |
| `TAVILY_API_KEY` | Yes | For web search ([Tavily](https://tavily.com)) |
| `API_BASE_URL` | No | FastAPI base URL for Streamlit (default: `http://localhost:8000`) |
| `DATABASE_URL` | V3+ | PostgreSQL connection string (see [Database setup](#database-setup-v3)) |

---

## How to run

| Option | Command | Description |
|--------|---------|-------------|
| **UI** | `streamlit run ui/Home.py` | Browser UI on port 8501. Requires FastAPI to be running first. |
| **API** | `uvicorn app.api:api --reload` | HTTP server on port 8000. Must be running for the UI to work. |
| **CLI** | `python scripts/run_graph.py "LangChain, LangGraph"` | Prints ideas to the terminal. Optional: `--count` (1–5), `--domain`, `--level`, `--enable-multi-query`, `--stream`, `--debug`. |

`GET /health` (liveness) and `GET /ready` (readiness — pings the database when `DATABASE_URL` is configured) are available once the API is running.

> **Note:** From V3-1 onwards, Streamlit calls FastAPI over HTTP. You must start **both** servers.

**Example (API):**

```bash
curl -X POST http://localhost:8000/ideas \
  -H "Content-Type: application/json" \
  -d '{"tech_stack": "React, Node.js, PostgreSQL", "domain": "fintech", "enable_multi_query": true, "count": 5}'
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

**Example (CLI with options):**

```bash
python scripts/run_graph.py "React, Node.js" --count 5 --domain fintech --level beginner --enable-multi-query
```

**Docs (when API is running):** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger), [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc).

---

## Architecture

### End-to-end flow

![Dev-Strom architecture flow](docs/architecture.png)

```
User input: "LangChain, LangGraph"
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LangGraph (app.invoke)                                                  │
│                                                                          │
│  START                                                                   │
│    │                                                                     │
│    ▼                                                                     │
│  fetch_web_context(state)                                                │
│    │  • Uses LangChain tool: web_search_project_ideas                    │
│    │  • If enable_multi_query=true: runs 2-3 queries                     │
│    │    ("project ideas", "tutorials", "example projects")               │
│    │    and merges with fair per-query cap                              │
│    │  • If enable_multi_query=false: single query (V1)                  │
│    │  • Calls Tavily API                                                 │
│    │  • Returns {"web_context": "..."}                                   │
│    ▼                                                                     │
│  generate_ideas(state)                                                   │
│    │  • Builds user_content = tech_stack + web_context                   │
│    │  • Invokes Deep Agent (LangGraph internally)                        │
│    │  • Deep Agent: LLM call with middleware (e.g. logging)              │
│    │  • Parses JSON → ProjectIdea objects                                │
│    │  • Returns {"ideas": [...]}                                         │
│    ▼                                                                     │
│  END                                                                     │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
Final state: {tech_stack, web_context, ideas}
```

**Step-by-step:**

1. **Input:** User provides a tech stack string (e.g. via UI, CLI, or API). Optional: `domain`, `level`, `enable_multi_query`, `count` (1–5).
2. **fetch_web_context:** LangGraph node reads `tech_stack` and `enable_multi_query`. If multi-query enabled, runs 2–3 queries ("project ideas for {stack}", "{stack} tutorials", "{stack} example projects") with fair per-query character limits, then merges results. If disabled, runs single query (V1 behavior). Calls the LangChain web search tool (Tavily), writes snippets to `web_context` in state.
3. **generate_ideas:** LangGraph node reads `tech_stack` and `web_context`, invokes the Deep Agent with a prompt; the agent returns JSON, which is parsed into `ProjectIdea` objects and written to `ideas` in state.
4. **Output:** Final state contains `tech_stack`, `web_context`, and `ideas` (1–5 ideas per run, per requested count).

### Layers

| Layer | Role |
|-------|------|
| **LangGraph** | Orchestration: state and node order (fetch_web_context → generate_ideas). |
| **LangChain** | Web search tool and prompts. |
| **Deep Agents** | Idea generation inside the `generate_ideas` node (with optional middleware). |

**Output schema** (`schema.py`): Each idea has `name`, `problem_statement`, `why_it_fits` (list), `real_world_value`, `implementation_plan` (list of steps). 1–5 ideas per run (configurable). API returns a `run_id` (UUID) with each ideas response; use it for `POST /expand` and `POST /export` so state is per-run and safe for concurrent clients.

---

## Project layout

Application code lives under `app/` (FastAPI server, LangGraph pipeline, database
services) and `ui/` (Streamlit frontend). `scripts/` holds standalone CLI entry
points; `migrations/` holds Alembic migrations.

| Path | Purpose |
|------|---------|
| `app/graph.py` | LangGraph pipeline: state, `fetch_web_context`, `generate_ideas`, `expand_idea`, model fallback chain. |
| `app/tools.py` | LangChain web search tool (Tavily). |
| `app/api.py` | FastAPI server: `POST /ideas`, `POST /expand`, `POST /export`, `GET /history`, `GET /runs/{run_id}`, `GET /health`, `GET /ready`. |
| `app/config.py` | Typed settings (`pydantic-settings`): API keys, `DATABASE_URL`, model + fallbacks, LangSmith config, log level. |
| `app/models/domain.py` | AI output models: `ProjectIdea`, `IdeasResponse`, `ExpandedIdea`. |
| `app/models/dto.py` | HTTP request DTOs: `IdeasRequest`, `ExpandRequest`, `ExportRequest`. |
| `app/services/db.py` | Lazily-created SQLAlchemy engine, session factory, `get_session()` context manager, `ping()`. |
| `app/services/models.py` | SQLAlchemy ORM models: `User`, `Run`, `ExpandedIdea` (and `web_chunks`, scaffolded — see [RAG status](#rag-status-web_chunks) below). |
| `app/services/run_service.py` | Run/expansion persistence: `save_run`, `save_expanded_idea`, `get_latest_expansion`, `load_history`, `get_run`. |
| `app/services/export_formatter.py` | Idea + extended plan → LLM-ready Markdown for download. |
| `ui/Home.py` | Streamlit UI entry point: generate, expand, download. |
| `ui/api_client.py` | HTTP client used by Streamlit to call FastAPI. |
| `ui/components.py` | Shared Streamlit UI components. |
| `ui/pages/` | Additional Streamlit pages (e.g. History). |
| `scripts/run_graph.py` | CLI entry point with `--stream` and `--debug` flags. |
| `scripts/test_web_search.py` | Smoke-tests the Tavily search tool in isolation. |
| `migrations/` | Alembic migration environment and versions (`001_initial_schema.py`, ...). |
| `docs/PLAN.md` | Full architecture plan (V1 → V3). |
| `docs/V1_TICKETS.md` | V1 Jira-style tickets. |
| `docs/V2_TICKETS.md` | V2 tickets (expand, export, multi-query, etc.). |
| `docs/V3_TICKETS.md` | V3 tickets (auth, DB, RAG, MCP, React). |
| `docs/Dev-Strom_API.postman_collection.json` | Postman collection for the API. |

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
retrieval node that reads from it. Web context currently comes only from the
live Tavily search in `fetch_web_context` (`app/tools.py`). Treat
`web_chunks` as scaffolding for a future ticket, not a working feature.

---

## License and docs

- **Plan and tickets:** [docs/PLAN.md](docs/PLAN.md), [docs/V1_TICKETS.md](docs/V1_TICKETS.md), [docs/V2_TICKETS.md](docs/V2_TICKETS.md), [docs/V3_TICKETS.md](docs/V3_TICKETS.md)
