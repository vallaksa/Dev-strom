# Dev-Strom — Master Project Plan

> This is the single source of truth for the Dev-Strom roadmap.
> All versions, decisions, and scope changes are tracked here.
> See `V1_TICKETS.md`, `V2_TICKETS.md`, `V3_TICKETS.md`, and `BACKLOG.md` for granular tickets.

---

## 🧠 Core Idea

A system that helps developers who want to learn a tech stack but don't know what to build.
The user enters a **tech stack** (and optional domain/level) and the system returns **concrete, grounded project ideas** — each with a problem statement, why the stack fits, real-world value, and an implementation plan.
Ideas are grounded in **live web search results** so they are practical and current.

---
## Branch nameing convention

`feature/DEVSTROM-Vx-x`
`fix/DEVSTROM-Vx-x`
`release/Vx`

---

## 📦 Version Summary

| Version | Status      | Theme                                      |
|---------|-------------|---------------------------------------------|
| V1      | ✅ Complete  | Core idea generator (MVP)                  |
| V2      | ✅ Complete  | Feature expansion + UX polish              |
| V3      | ✅ Complete  | Postgres, history, MCP (auth/RAG descoped) |
| F1–F4   | ✅ Complete  | Cartographer, Advisor, React UI, async jobs |
| Neo4j live store | ✅ Wired, opt-in | CartographStore factory + Docker daemon |
| V4      | 📋 Next     | Neo4j GraphRAG (not the Cartographer store) |

---

---

## Where we are (2026-08-19)

V1–V3 (reduced V3 scope) and F1–F4 are in `main`. Cartographer still **defaults to Postgres JSONB**. Neo4j is installed on the server as a Docker daemon and is an **opt-in** CartographStore backend. Making Neo4j the default is a later decision, not part of wiring.

### What actually runs on the server

```
Browser  →  React (web/, :5173) and/or Streamlit (ui/, :8501)
                │
                ▼
         FastAPI (app.api, :8000)
                │
     ┌──────────┼──────────────┐
     ▼          ▼              ▼
 Postgres    Neo4j          postgres-mcp
 (Docker,    (Docker,       (Docker, :3000)
  :5432,      :7474/:7687,
  global-     global-
  network)    network)
```

Both databases are standalone Docker daemons on `global-network` with `restart: unless-stopped`. They are **not** started by Dev-Strom `docker-compose.yml`. Compose `db` is the portable/dev template; this server uses the existing `postgres` container. Neo4j is the container named `neo4j` (image `neo4j:5`).

### API surface (shipped)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/ideas` | Idea generation |
| POST | `/expand` | Expand one idea by pid |
| POST | `/export` | Markdown export |
| GET | `/history`, `/runs/{run_id}` | Persisted runs |
| POST | `/cartograph` | Architecture graph; optional `?async=true` |
| GET | `/cartograph/{run_id}` | Load a cartograph run |
| POST | `/analyze` | Evidence-first Repository Intelligence: deterministic ingest → `Analysis` (Repository + evidence-backed Findings + Recommendations) + component `mermaid` + structural `graph`; optional `?async=true` |
| GET | `/analyze/{run_id}` | Load an analysis run (same flat body as POST) |
| GET | `/analyses` | List recent analysis runs as summary rows (History), paged like `/history` |
| POST | `/advise` | Improvement advisor; optional `?async=true` |
| GET | `/advise/{run_id}` | Load an advisor run |
| GET | `/jobs/{job_id}` | Poll async jobs |

`POST /ideas` also accepts a natural-language `intent` (the NL-first input; `tech_stack` is now optional, at least one required) and returns idea cards enriched with `business_value` / `engineering_challenges` / `architectural_intent` / `tradeoffs`.
| GET | `/health`, `/ready` | Liveness / Postgres ping |

### Cartographer persistence

| Backend | When | Store |
|---------|------|--------|
| `postgres` (default) | `CARTOGRAPH_STORE_BACKEND` unset or `postgres` | `PostgresJsonbStore` |
| `neo4j` | `CARTOGRAPH_STORE_BACKEND=neo4j` | `Neo4jStore` via `get_cartograph_store()` |

`app/api.py` always calls `get_cartograph_store()`. Flipping the env var is the only app change needed to persist graphs in Neo4j. The F3 React UI does not care which backend is behind GET `/cartograph/{run_id}`.

Live Neo4j round-trip is covered by `tests/integration/test_neo4j_live.py`, skipped when Bolt is unreachable so CI stays hermetic.

### Not done yet (do not confuse with the above)

- **V4 Neo4j GraphRAG** (`BACKLOG.md`) — entity/relationship extraction into a knowledge graph, replacing `web_chunks`. Infra (Neo4j daemon) is ready; the product feature is not.
- **Google OAuth / JWT / key vault / per-user cache** — still deferred; anonymous user UUID.
- **pgvector RAG pipeline** — `web_chunks` table exists; nothing writes or retrieves embeddings.
- **Neo4j as the default CartographStore** — explicit later decision.

---

# ✅ V1 — MVP (Complete)

## What Was Built

A minimal but working idea generator. User enters a tech stack, the system searches the web and generates 3 project ideas using a LangGraph pipeline and a Deep Agent.

## Architecture

```
User Input (tech_stack)
     ↓
[LangGraph Pipeline]
     ├── Node 1: fetch_web_context  → Tavily web search → stores in state
     └── Node 2: generate_ideas    → DeepAgent + OpenAI LLM → returns 3 ideas as JSON
     ↓
Output: 3 project ideas (name, problem, why_it_fits, value, plan)
```

## Tech Stack

| Layer        | Technology                          |
|--------------|-------------------------------------|
| Orchestration| LangGraph                           |
| Agent        | DeepAgents (`create_deep_agent`)    |
| LLM          | OpenAI GPT (via DeepAgent)          |
| Web Search   | Tavily API                          |
| Schema       | Pydantic (`ProjectIdea`, `IdeasResponse`) |
| API          | FastAPI (`POST /ideas`, `POST /expand`, `POST /export`) |
| UI           | Streamlit (`ui.py`)                 |
| Config       | python-dotenv (`.env`)              |

## Files Delivered

| File                | Purpose                                         |
|---------------------|-------------------------------------------------|
| `graph.py`          | LangGraph pipeline (nodes, state, graph build)  |
| `tools.py`          | Tavily web search LangChain tool                |
| `schema.py`         | Pydantic models (ProjectIdea, IdeasResponse, ExpandedIdea) |
| `api.py`            | FastAPI endpoints (ideas, expand, export)        |
| `ui.py`             | Streamlit browser UI                            |
| `export_formatter.py` | Markdown export formatter                     |
| `.env.example`      | Environment variable template                   |
| `requirements.txt`  | Python dependencies                             |

## V1 Tickets (All Complete)

| Key        | Title                                 | Done |
|------------|---------------------------------------|------|
| DEVSTROM-1 | Project setup and output schema       | [x]  |
| DEVSTROM-2 | Web search tool (LangChain + Tavily)  | [x]  |
| DEVSTROM-3 | LangGraph (fetch_web_context + generate_ideas) | [x] |
| DEVSTROM-4 | DeepAgent integration and middleware  | [x]  |
| DEVSTROM-5 | FastAPI endpoint (POST /ideas)        | [x]  |
| DEVSTROM-6 | Streamlit UI                          | [x]  |

---

---

# ✅ V2 — Feature Expansion (Complete)

## What V2 Adds

V2 extends V1 with richer inputs, smarter web context, more control over output, export, history, caching, and reliability. **No breaking changes to V1 behavior.**

## V2 Scope at a Glance

| Key            | Title                               | Status           |
|----------------|-------------------------------------|------------------|
| DEVSTROM-V2-1  | Optional domain and level input     | ✅ Done                      |
| DEVSTROM-V2-2  | Web context summarization (themes)  | ⏸️ Pending quality eval      |
| DEVSTROM-V2-3  | Multi-query web context             | ✅ Done                      |
| DEVSTROM-V2-4  | Configurable idea count + expand    | ✅ Done                      |
| DEVSTROM-V2-5  | Export expanded idea as Markdown    | ✅ Done                      |
| DEVSTROM-V2-6  | Session history + persistence       | ⏭️ Skipped → absorbed into V3 (DEVSTROM-V3-5) |
| DEVSTROM-V2-7  | Shareable link (input params)       | ❌ Dropped — not needed       |
| DEVSTROM-V2-8  | Retry and schema validation         | ❌ Dropped — not needed now   |
| DEVSTROM-V2-9  | Caching by input key                | ⏭️ Skipped → absorbed into V3 (DEVSTROM-V3-9) |
| DEVSTROM-V2-10 | Structured logging and tracing      | ❌ Dropped — premature for now|

**V2 Progress: 4/10 done, rest closed.** History and caching were absorbed into V3; remaining V2 tickets were dropped. V2 is complete.

## V2 Decisions Made

- `@st.cache_data` added in `ui.py` for in-session caching (same inputs → instant result without API call).
- `@lru_cache` on agent getters (`_get_idea_agent`, `_get_expand_agent`) for singleton agent objects (avoids repeated setup cost, not caching results).
- Markdown fence stripping uses `\A` / `\Z` anchors (not `re.MULTILINE`) to avoid corrupting JSON responses from the LLM.
- Streamlit originally called `graph_app.invoke()` directly. **Fixed in V3-1:** Streamlit talks to FastAPI over HTTP (`ui/api_client.py`).

---

# ✅ V3 — Platform (Complete, reduced scope)

Original V3 imagined auth, RAG, MCP, and React as one milestone. **What shipped as V3** is the 7 tickets in `V3_TICKETS.md`: FastAPI decoupling, Postgres + Alembic, run history, Streamlit History, and MCP dedup. Auth, key vault, RAG retrieval, TTL cache, and the original React tickets were moved to `BACKLOG.md`. React later shipped as F3 (no auth). The diagrams below are the **original V3 design**, kept for history — they are not a description of production today. For production, use [Where we are](#where-we-are-2026-08-19).

## Why V3 Exists

V2 proves the product. V3 makes it a real platform:
- Multi-user auth (Google OAuth)
- User-owned API keys (no shared keys, no cost liability)
- Per-user idea history stored in a real database
- Real RAG pipeline (semantic chunking + vector search) instead of raw string trimming
- PostgreSQL accessed by the LLM agent via MCP (learning MCP)
- React UI (same FastAPI backend — Streamlit becomes optional/admin-only)

---

## V3 Architecture (original design — not production)

```
┌──────────────────────────────────────────────────────────────────┐
│            FRONTEND (Streamlit now → React/Vite later)          │
│   Home (ideas) | History | Settings (profile + API keys)        │
│          Auth gate: must be logged in to use any page           │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP + JWT
┌────────────────────────▼─────────────────────────────────────────┐
│                     FastAPI Backend                              │
│                                                                  │
│  Auth:     POST /auth/google  GET /auth/me  POST /auth/logout    │
│  Vault:    GET /vault/keys    POST /vault/keys  DELETE /vault/keys│
│  Ideas:    POST /ideas   POST /expand   POST /export             │
│  History:  GET /history  GET /runs/{id}                          │
│                                                                  │
│  Middleware: JWT validation on all routes except /auth/*         │
└───────┬──────────────────────┬────────────────────────────────────┘
        │                      │
┌───────▼──────┐    ┌──────────▼─────────────────────────────────┐
│  Cache Layer │    │           LangGraph Pipeline (enhanced)     │
│  TTLCache    │    │                                             │
│  key = hash( │    │  [fetch_web_context]                        │
│  user_id +   │    │    ├─ Tavily search (user's own key)        │
│  params)     │    │    ├─ Chunk text into paragraphs           │
│  TTL: 1hr    │    │    ├─ Embed chunks (OpenAI embeddings)      │
└──────────────┘    │    └─ Store vectors in pgvector             │
                    │                                             │
                    │  [generate_ideas]                           │
                    │    ├─ MCP: query Postgres for user history  │
                    │    ├─ pgvector: semantic search top-K chunks│
                    │    └─ DeepAgent + OpenAI → ideas JSON       │
                    └─────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────┐
│             PostgreSQL + pgvector (self-hosted)                 │
│                                                                 │
│  users            google_id, email, name, avatar, timestamps   │
│  user_api_keys    user_id, provider, encrypted_key             │
│  runs             user_id, inputs, ideas (JSONB), timestamp    │
│  expanded_ideas   run_id, pid, extended_plan (JSONB)           │
│  web_chunks       run_id, content, embedding (vector(1536))    │
│                                                                 │
│           ↑ accessed by Python app via SQLAlchemy              │
│           ↑ accessed by LLM agent via MCP Postgres server      │
└─────────────────────────────────────────────────────────────────┘
```

---

## V3 Tech Stack

| Layer              | Technology                        | Why                                      |
|--------------------|-----------------------------------|------------------------------------------|
| Frontend (now)     | Streamlit (calls FastAPI via HTTP)| Keep existing UI, decouple from graph    |
| Frontend (future)  | React + Vite                      | Same FastAPI backend, no backend changes |
| Backend API        | FastAPI + JWT (python-jose)       | Already exists, add auth middleware      |
| Auth               | Google OAuth2 (authlib)           | Industry standard, no password to manage |
| Database           | PostgreSQL (self-hosted)          | Relational + extensible                  |
| Vector search      | pgvector (Postgres extension)     | No separate vector DB, single system     |
| Embeddings         | OpenAI `text-embedding-3-small`   | Same API key user already provides       |
| Encryption         | Fernet (Python cryptography lib)  | AES-128 for API key storage              |
| DB ORM             | SQLAlchemy Core + Alembic         | Migrations, type safety, no magic        |
| DB access (AI)     | MCP Postgres server               | LLM queries DB directly via MCP tools   |
| Caching            | cachetools.TTLCache               | Per-user, TTL-based, in-process          |
| Agent              | DeepAgents (unchanged)            | Keep existing pattern                    |
| Orchestration      | LangGraph (unchanged)             | Keep existing graph                      |

---

## V3 Database Schema

```sql
-- Who logged in via Google
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id   TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Encrypted API keys per user, per provider
CREATE TABLE user_api_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
    provider      TEXT NOT NULL,           -- 'openai' | 'tavily'
    encrypted_key TEXT NOT NULL,           -- Fernet encrypted
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, provider)
);

-- Every generation run
CREATE TABLE runs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID REFERENCES users(id) ON DELETE CASCADE,
    tech_stack         TEXT NOT NULL,
    domain             TEXT,
    level              TEXT,
    count              INT DEFAULT 3,
    enable_multi_query BOOLEAN DEFAULT false,
    ideas              JSONB NOT NULL,
    web_context        TEXT,
    created_at         TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_runs_user_id    ON runs(user_id);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);

-- Expanded ideas (linked to run + position)
CREATE TABLE expanded_ideas (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID REFERENCES runs(id) ON DELETE CASCADE,
    pid           INT NOT NULL,
    extended_plan JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(run_id, pid)
);

-- Web search content as vector chunks (pgvector RAG)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE web_chunks (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id    UUID REFERENCES runs(id) ON DELETE CASCADE,
    content   TEXT NOT NULL,
    embedding vector(1536) NOT NULL     -- OpenAI text-embedding-3-small
);
CREATE INDEX idx_web_chunks_embedding ON web_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
```

---

## V3 Auth Flow

```
User visits app
  └─ Logged in? (JWT in session_state)
        Yes → render app normally
        No  → show "Login with Google" button
                └─ Google OAuth2 flow (authlib)
                      └─ Google returns: email, name, google_id, avatar
                            └─ DB: upsert user row
                                  └─ Load encrypted API keys from DB
                                        └─ Decrypt → store in session_state["keys"]
                                              └─ Has both keys?
                                                    No  → redirect to ⚙️ Settings
                                                    Yes → render app normally
```

**Security rule:** Decrypted keys live ONLY in `session_state` (browser memory).
They are never written back to the DB after initial load. If session expires, user re-auths and keys are re-decrypted fresh from DB.

---

## V3 User-Facing UI Structure

```
app.py                     ← Auth gate (redirects to login if no JWT)
pages/
  1_🏠_Home.py             ← Idea generator (current ui.py, calls FastAPI)
  2_📋_History.py          ← Per-user run history, clickable to view ideas
  3_⚙️_Settings.py         ← Profile info + API key vault (add/update/delete keys)
services/
  auth.py                  ← Google OAuth helpers, JWT create/verify
  db.py                    ← SQLAlchemy engine + session factory
  key_vault.py             ← Fernet encrypt/decrypt for API keys
  run_service.py           ← save_run(), load_history(), get_run()
  cache.py                 ← TTLCache singleton, get/set/invalidate
```

---

## V3 Caching Strategy

```
User clicks "Get Ideas"
  └─ Compute cache_key = sha256(user_id + tech_stack + domain + level + count + multi_query)
        └─ L1 hit? (TTLCache, 1hr TTL) → return instantly (<5ms)
              No → L2 hit? (runs table, same params in last 24hr) → return from DB (<50ms)
                    No → run full graph (Tavily + embeddings + LLM) → save to L1 + L2
```

---

## V3 MCP Integration (Learn MCP)

MCP (Model Context Protocol, by Anthropic) lets the LLM agent query your PostgreSQL database directly using structured tool calls — instead of Python code fetching data and feeding it as a string.

```
Agent needs context → calls MCP tool: query_user_history(user_id, tech_stack)
                          └─ MCP Postgres server executes SQL
                                └─ Returns: past ideas for similar stacks
                                      └─ Agent uses this to avoid repeating ideas
```

**What this teaches:** How MCP works, how agents use tools against external systems, and how to build your own MCP server.
**Setup:** `@modelcontextprotocol/server-postgres` (official Postgres MCP server).

---

## V3 RAG Pipeline (Replace Raw String with Semantic Retrieval)

**Current (V1/V2):**
```
Tavily → raw text → trimmed at 6000 chars → fed to LLM prompt
```

**V3 (Real RAG):**
```
Tavily → chunk text into ~500 char paragraphs
       → embed each chunk (OpenAI text-embedding-3-small)
       → store in pgvector (web_chunks table)
       → at generation time: embed user query
       → vector similarity search → top-5 most relevant chunks
       → feed ONLY those chunks to LLM prompt
```

**Why this is better:** LLM gets the most *relevant* parts of web content for the specific query — not just the first N characters of a raw dump. Ideas are richer and more grounded.

---

## V3 Implementation Phases

### Phase 1 — Decouple UI from Graph (Critical, Do First)
> Streamlit must call FastAPI HTTP endpoints — never `graph.py` directly.
> This unlocks the React swap with zero backend changes.
- `ui.py` uses `httpx` or `requests` to call `POST /ideas`, `POST /expand`, `POST /export`
- FastAPI handles auth (JWT) and keys — Streamlit only handles display
- After this: any frontend (Streamlit, React, CLI, mobile) works with the same backend

### Phase 2 — PostgreSQL Setup + pgvector
- Install PostgreSQL, enable pgvector extension
- Write Alembic migrations for all 5 tables
- `services/db.py` — SQLAlchemy engine + session
- Smoke test: insert a user row, query it back

### Phase 3 — Google OAuth + JWT
- Register app in Google Cloud Console → get `CLIENT_ID` + `CLIENT_SECRET`
- `services/auth.py` — OAuth2 flow, JWT issue/verify
- FastAPI: `POST /auth/google`, `GET /auth/me`, `POST /auth/logout`
- Streamlit: login page → redirect flow → store JWT in `session_state`

### Phase 4 — Key Vault
- `services/key_vault.py` — Fernet encrypt/decrypt
- `VAULT_SECRET_KEY` in `.env` (server-side encryption key, never shared)
- FastAPI: `GET /vault/keys` (masked), `POST /vault/keys` (encrypt + store), `DELETE /vault/keys`
- Settings page in Streamlit: add/update/delete OpenAI + Tavily keys
- After login: load keys → decrypt → store in `session_state["keys"]`
- Graph/tools: read keys from `session_state["keys"]` not from `.env`

### Phase 5 — Per-User History (V2-6, done properly)
- After every successful graph run: `run_service.save_run(user_id, inputs, ideas)`
- FastAPI: `GET /history` (paginated), `GET /runs/{id}`
- Streamlit History page: list of past runs with tech_stack + timestamp, click to view

### Phase 6 — RAG: Chunking + Embedding
- After Tavily search: chunk text → embed → store in `web_chunks` (pgvector)
- Chunking strategy: ~500 char windows with overlap
- Embedding: `openai.embeddings.create(model="text-embedding-3-small", ...)`

### Phase 7 — RAG: Semantic Retrieval at Generate Time
- At `generate_ideas` time: embed the user query → pgvector similarity search → top-5 chunks
- Pass retrieved chunks to LLM prompt instead of raw `web_context` dump

### Phase 8 — MCP Postgres Server
- Set up `@modelcontextprotocol/server-postgres` pointing to local Postgres
- Register MCP as a tool in the DeepAgent for `generate_ideas`
- Agent can call: `get_user_history(tech_stack)` → avoids repeating past ideas

### Phase 9 — Caching Layer (V2-9, proper multi-user version)
- `services/cache.py` — `cachetools.TTLCache` singleton, keyed by `user_id + params hash`
- FastAPI layer checks cache before invoking graph; stores result on miss
- TTL configurable via env var (default: 1 hour)

### Phase 10 — React UI (Vite + TypeScript)
- New `frontend/` directory with Vite React project
- Pages: Login, Home, History, Settings — mirror current Streamlit pages
- Calls same FastAPI endpoints (no backend changes needed)
- JWT stored in `localStorage` / `httpOnly cookie`
- Streamlit kept as optional admin/debug UI

---

## V3 Tickets

> Original 19-ticket design below. **What actually shipped:** 7 tickets in `V3_TICKETS.md` (V3-1..V3-7: decouple UI, Postgres, Alembic, history API, History page, MCP server, MCP in agent). Auth/RAG/React-as-V3 tickets were descoped; React later shipped as F3 without auth.

| Key             | Title                                            | Phase |
|-----------------|--------------------------------------------------|-------|
| DEVSTROM-V3-1   | Decouple Streamlit → FastAPI HTTP calls          | 1     |
| DEVSTROM-V3-2   | PostgreSQL install + db.py connection service    | 2     |
| DEVSTROM-V3-3   | Alembic setup + all 5 table migrations           | 2     |
| DEVSTROM-V3-4   | Google OAuth2 + JWT service (backend)            | 3     |
| DEVSTROM-V3-5   | JWT middleware + protect existing API routes     | 3     |
| DEVSTROM-V3-6   | Streamlit login page + JWT session handling      | 3     |
| DEVSTROM-V3-7   | API Key Vault — service + FastAPI routes         | 4     |
| DEVSTROM-V3-8   | Streamlit Settings page (key management UI)      | 4     |
| DEVSTROM-V3-9   | Wire graph + tools to use user-supplied keys     | 4     |
| DEVSTROM-V3-10  | Run service + FastAPI history endpoints          | 5     |
| DEVSTROM-V3-11  | Streamlit History page                           | 5     |
| DEVSTROM-V3-12  | Web chunking + embedding + pgvector storage      | 6     |
| DEVSTROM-V3-13  | Semantic retrieval at idea-generation time       | 7     |
| DEVSTROM-V3-14  | Setup MCP Postgres server (standalone)           | 8     |
| DEVSTROM-V3-15  | Integrate MCP into DeepAgent                    | 8     |
| DEVSTROM-V3-16  | Per-user TTL caching layer (cachetools)          | 9     |
| DEVSTROM-V3-17  | React + Vite scaffold + routing + API client     | 10    |
| DEVSTROM-V3-18  | React auth (login page + JWT flow)               | 10    |
| DEVSTROM-V3-19  | React Home + History + Settings pages            | 10    |


---

## What V3 Teaches You

By the end of V3, you will have built and understood:

| Technology            | Where You Learn It                       |
|-----------------------|------------------------------------------|
| Google OAuth2 / JWT   | Auth flow (Phase 3)                      |
| PostgreSQL + Alembic  | Schema design + migrations (Phase 2)     |
| pgvector              | Vector similarity search (Phase 6–7)     |
| OpenAI Embeddings     | How semantic search works (Phase 6)      |
| RAG pipeline          | The #1 pattern in production AI (Phase 6–7) |
| MCP Protocol          | LLM ↔ database via tools (Phase 8)       |
| FastAPI + Middleware   | JWT auth, layered API design (Phase 1–4) |
| React + Vite          | Modern frontend development (Phase 10)   |
| cachetools            | TTL caching in Python (Phase 9)          |

---

---

# Post-V3 — F1–F4 (Complete)

Shipped on `main` after the reduced V3 set. Numbering is the feature series used in merge commits, not Jira keys.

| Feature | What shipped |
|---------|----------------|
| **F1 Cartographer** | `POST /cartograph` + `GET /cartograph/{run_id}`. Graph persisted by `CartographStore`. Default backend: Postgres JSONB. |
| **F1-4 Neo4j adapter** | `Neo4jStore` (native `:CartographRun` / `:GraphNode` / dynamic rels) and `get_cartograph_store()`. Selected with `CARTOGRAPH_STORE_BACKEND=neo4j`. |
| **F2 Advisor** | `POST /advise` + `GET /advise/{run_id}` plus Streamlit Advisor page. |
| **F3 React UI** | Vite/React/TS app in `web/`: Ideas, History, Cartographer (React Flow), Advisor. Same FastAPI backend. Streamlit remains. |
| **F4 Jobs** | In-process `create_job` / `get_job` / `run_job`. Opt-in `?async=true` on `/cartograph` and `/advise`; poll `GET /jobs/{job_id}`. |

## Neo4j live store (2026-08-19)

This is **not** GraphRAG. It is the Cartographer persistence backend plus server infra.

1. Neo4j runs as Docker container `neo4j` (`neo4j:5`) on `global-network`, same network as `postgres`, `restart: unless-stopped`, ports `7474` / `7687`, volume `neo4j_data`.
2. `Neo4jStore` save→get was smoke-tested against that instance (run-scoped merge keys, `ProjectGraph` round trip).
3. `app/api.py` uses `get_cartograph_store()`.
4. Default remains `CARTOGRAPH_STORE_BACKEND=postgres`. Documented in `.env.example` and README.
5. Endpoint e2e (LLM mocked, real Neo4j) confirmed GET shape matches what the F3 UI already consumes.
6. Gated live test: `tests/integration/test_neo4j_live.py`.
7. **Not done:** flipping the default to Neo4j.

Host Bolt URI: `neo4j://localhost:7687`. From another container on `global-network`: `neo4j://neo4j:7687`. Auth matches `NEO4J_AUTH` (default `neo4j/devstrom`).

---

# V4 — Next

Flagship: **Neo4j GraphRAG** in `BACKLOG.md` (entities/relationships from web context, vector index + traversal). That work can use the Neo4j daemon already running. Do not treat Cartographer's optional `Neo4jStore` as GraphRAG.

Still deferred: Google OAuth/JWT, API key vault, pgvector retrieval, Redis/queue workers, making Neo4j the CartographStore default.

---

*Last updated: 2026-08-19. Update this file as decisions are made or scope changes.*
