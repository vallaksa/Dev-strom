# Dev-Strom V3 — Jira-style Tickets

> Work through tickets in order. Each ticket is self-contained with a concept explanation inside the Description, acceptance criteria, and plain-English instructions. Mark `[ ]` → `[x]` when done.
> **V3-1, V3-2, V3-3** are hard prerequisites — complete them before anything else.
> Until auth is implemented, all features use a hardcoded anonymous user UUID.

---

## Ticket Summary

| Key             | Title                                            | Done | Depends on     |
|-----------------|--------------------------------------------------|------|----------------|
| DEVSTROM-V3-1   | Decouple Streamlit → FastAPI HTTP calls          | [x]  | None           |
| DEVSTROM-V3-2   | PostgreSQL install + db.py connection service    | [x]  | None           |
| DEVSTROM-V3-3   | Alembic setup + all 5 table migrations           | [x]  | V3-2           |
| DEVSTROM-V3-4   | Run service + FastAPI history endpoints          | [x]  | V3-3           |
| DEVSTROM-V3-5   | Streamlit History page                           | [x]  | V3-4           |
| DEVSTROM-V3-6   | Setup MCP Postgres server (standalone)           | [x]  | V3-3           |
| DEVSTROM-V3-7   | Integrate MCP into DeepAgent                     | [x]  | V3-6, V3-4     |

**V3 Progress: 7/7 complete**

---

---

## DEVSTROM-V3-1 — Decouple Streamlit → FastAPI HTTP Calls

- [x] **Ticket completed**

**Type:** Architecture refactor
**Priority:** Highest — must be done first
**Depends on:** None

### Description

Currently `ui.py` imports `graph.py` directly and calls the graph as a Python function. This tightly couples the Streamlit UI to the backend. If you later swap Streamlit for React, you'd need to rewrite all graph-calling logic in the new frontend.

The fix is to make Streamlit call FastAPI over HTTP, exactly like any other client (React, mobile app, CLI) would. The UI becomes a pure display layer with no knowledge of the graph internals. All business logic stays in FastAPI. This is the pattern that makes any future frontend swap completely seamless — zero backend changes required.

A thin `services/api_client.py` module will handle all HTTP calls so the Streamlit pages only need to call functions like `get_ideas(payload)` or `expand_idea(run_id, pid)` without knowing anything about the underlying HTTP details.

### Acceptance Criteria

- [x] `ui.py` contains zero imports from `graph.py` or `tools.py`.
- [x] All network calls go through a new `services/api_client.py` module using the `httpx` library.
- [x] The FastAPI base URL is read from an `API_BASE_URL` environment variable, defaulting to `http://localhost:8000`.
- [x] The `run_id` returned by the `/ideas` endpoint is stored in Streamlit session state and passed to all subsequent expand and export calls.
- [x] The full app flow (generate → expand → download) works end-to-end with both servers running simultaneously.
- [x] `API_BASE_URL` is documented in `.env.example`.

### Instructions

1. Add `httpx` to `requirements.txt`.
2. Create a `services/` folder in the project root if it does not already exist.
3. Create `services/api_client.py` with individual functions for each FastAPI endpoint: one for fetching ideas, one for expanding an idea, and one for exporting. Each function takes the relevant parameters, makes an HTTP POST call to the FastAPI server, raises an error if the response is not successful, and returns the parsed JSON or text response.
4. Update `ui.py` to import and use `api_client` functions instead of calling the graph directly. Remove all imports from `graph.py` and `tools.py`.
5. Store the `run_id` field from the `/ideas` response in `st.session_state` so it is available when the user clicks Expand or Export.
6. Add `API_BASE_URL=http://localhost:8000` to `.env.example`.
7. Test by starting the FastAPI server and the Streamlit server in separate terminals. Verify the complete flow works without errors.

---

---

## DEVSTROM-V3-2 — PostgreSQL Install + `services/db.py` Connection Service

- [x] **Ticket completed**

**Type:** Infrastructure
**Priority:** Highest — required before all database-dependent tickets
**Depends on:** None (can be done in parallel with V3-1)

### Description

PostgreSQL is a relational database that stores data in tables with rows and columns, linked together by foreign keys. It is the most widely used production database in professional software projects.

This ticket sets up the PostgreSQL server locally and creates a Python service module that the rest of the application uses to open and close database connections. Rather than connecting to the database directly from multiple places in the code, a single `services/db.py` module manages the connection pool and exposes a clean interface for running queries safely.

The `pgvector` extension is also enabled in this ticket. It is a PostgreSQL plugin that adds a special column type for storing vector embeddings, which will be used later in the RAG (semantic search) tickets.

SQLAlchemy is the Python library used to communicate with PostgreSQL. It handles low-level connection management and lets the rest of the code use Python objects instead of raw SQL strings.

### Acceptance Criteria

- [x] PostgreSQL is running locally and accessible. A database named `devstrom` exists.
- [x] The `pgvector` extension is enabled inside the `devstrom` database.
- [x] The `psycopg2-binary`, `sqlalchemy>=2.0`, `pgvector`, and `alembic` packages are added to `requirements.txt`.
- [x] `services/db.py` exists and exposes a SQLAlchemy engine and a `get_session()` context manager for safe database access.
- [x] The `DATABASE_URL` environment variable is the only place the connection string is defined — no hardcoded values anywhere in the codebase.
- [x] A simple connectivity test (connecting and running a basic query) passes without errors.
- [ ] `DATABASE_URL` is documented in `.env.example`.

### Instructions

1. Install PostgreSQL locally using Docker or the system package manager. Create a database named `devstrom` and confirm it is accessible.
2. Connect to the `devstrom` database and run the command to enable the `vector` extension (part of pgvector). Confirm it is listed as an installed extension.
3. Add the four required packages to `requirements.txt` and install them.
4. Create `services/db.py`. This file should define a SQLAlchemy engine using the `DATABASE_URL` environment variable, a session factory, a `Base` class for ORM models, and a `get_session()` context manager that automatically commits on success and rolls back on error.
5. Write a simple script or one-liner that imports the engine and runs a trivial query (such as `SELECT 1`) to confirm the connection is working.
6. Add `DATABASE_URL=postgresql://postgres:devstrom@localhost:5432/devstrom` to `.env.example`.

---

---

## DEVSTROM-V3-3 — Alembic Setup + All 5 Table Migrations

- [x] **Ticket completed**

**Type:** Infrastructure
**Priority:** Highest
**Depends on:** V3-2

### Description

A database migration is a versioned file that describes a change to the database schema — creating a table, adding a column, or modifying an index. Alembic is Python's standard migration tool. Instead of manually running SQL `CREATE TABLE` commands every time a new server is set up, you run a single Alembic command and all migrations apply automatically in order.

This ticket creates the initial migration that defines all five tables for the Dev-Strom V3 database: `users`, `user_api_keys`, `runs`, `expanded_ideas`, and `web_chunks`. The schema for each table is described in `PLAN.md`.

### Acceptance Criteria

- [x] Alembic is initialized in the project root. The `alembic.ini` configuration file and `migrations/` directory both exist.
- [x] Alembic is configured to read `DATABASE_URL` from the environment rather than using a hardcoded connection string.
- [x] The initial migration file creates all five tables with the correct columns, data types, foreign keys, unique constraints, and indexes as defined in `PLAN.md`.
- [x] The `web_chunks.embedding` column uses the `vector(1536)` type provided by the pgvector SQLAlchemy integration.
- [x] Running `alembic upgrade head` on a fresh database creates all five tables without errors.
- [x] Running `alembic downgrade -1` removes the tables cleanly.
- [x] `alembic upgrade head` is idempotent — running it twice does not cause errors.

### Instructions

1. Run `alembic init migrations` in the project root to create the Alembic scaffold.
2. Edit `alembic.ini` to remove the hardcoded `sqlalchemy.url` value and replace it with a reference to the `DATABASE_URL` environment variable.
3. Edit `migrations/env.py` to load the `.env` file using `python-dotenv` and set the SQLAlchemy URL from the environment before Alembic runs any migrations.
4. Create the initial migration file either by running Alembic's autogenerate command or writing it manually. The migration must include all five tables from the schema in `PLAN.md`: `users`, `user_api_keys`, `runs`, `expanded_ideas`, and `web_chunks`.
5. Ensure UUID primary keys use `gen_random_uuid()` as the default, foreign keys use `ON DELETE CASCADE`, and the `web_chunks.embedding` column is typed as `vector(1536)` using the pgvector SQLAlchemy type.
6. Add the IVFFlat index on `web_chunks.embedding` for fast similarity search, and standard B-tree indexes on `runs.user_id` and `runs.created_at DESC`.
7. Run `alembic upgrade head` and verify all five tables appear in the database.
8. Run `alembic downgrade -1` and verify the tables are removed. Then run `alembic upgrade head` again to confirm idempotency.

---

---

## DEVSTROM-V3-4 — Run Service + FastAPI History Endpoints

- [x] **Ticket completed**

**Type:** Feature
**Priority:** High
**Depends on:** V3-3

### Description

Every time a user clicks "Get Ideas", the result — inputs and generated ideas — is saved to the `runs` table. This is a simple insert after the graph finishes. The ideas are stored as JSONB, PostgreSQL's queryable JSON column type.

Once runs are persisted, the history endpoints let the user retrieve past results. They never need to re-run the graph to see an old result — the ideas are loaded from the database instantly and for free.

Until auth is implemented, all runs are saved under a hardcoded anonymous user UUID. When auth is added later, the UUID simply comes from the JWT instead.

### Acceptance Criteria

- [x] A hardcoded anonymous user is seeded into the `users` table (via a migration or startup script) so foreign key constraints are satisfied.
- [x] `services/run_service.py` exists with a `save_run` function that inserts a new row into `runs` and returns the generated `run_id`.
- [x] The FastAPI `/ideas` handler calls `save_run` after a successful graph result. The `run_id` is included in the response.
- [x] `GET /history` returns runs for the anonymous user, most recent first, with support for `limit` and `offset` query parameters. Default limit is 20.
- [x] `GET /runs/{run_id}` returns the full details of a single run including all ideas. Returns 404 if the run does not exist.
- [x] Expanded ideas created via `POST /expand` are persisted to the `expanded_ideas` table, linked to the `run_id` and idea position.

### Instructions

1. Create `services/models.py` with SQLAlchemy ORM model classes for `User`, `Run`, and `ExpandedIdea` that map to the corresponding database tables.
2. Seed an anonymous user into the `users` table — either via a new Alembic migration or a startup function in `db.py` that inserts the row if it doesn't exist. Use a fixed UUID constant (e.g. `00000000-0000-0000-0000-000000000000`) and a placeholder email like `anonymous@devstrom.local`.
3. Create `services/run_service.py` with three functions: a `save_run` function that inserts a row into `runs` using the anonymous user ID and returns the run ID as a string; a `load_history` function that queries runs by user ID in descending creation order with limit and offset; and a `get_run` function that fetches a single run by ID.
4. Update the `/ideas` handler to call `save_run` after the graph returns successfully. Add the `run_id` to the response body.
5. Add `GET /history` and `GET /runs/{run_id}` routes to `api.py`. The history route supports `limit` and `offset` query parameters. The run detail route returns 404 if not found.
6. Update the `/expand` handler to save the expanded result to the `expanded_ideas` table using the `run_id` and position index from the request.

---

---

## DEVSTROM-V3-5 — Streamlit History Page

- [x] **Ticket completed**

**Type:** Feature
**Priority:** Medium
**Depends on:** V3-4

### Description

The history page is the display layer for the data built in V3-4. It fetches past runs and displays them as a navigable list. Clicking a past run loads the stored ideas without any new API or LLM calls — everything is served from the database instantly.

### Acceptance Criteria

- [x] `pages/2_📋_History.py` exists and is reachable from the Streamlit sidebar.
- [x] The page fetches and displays a list of past runs, showing the tech stack and creation timestamp for each.
- [x] Clicking a run fetches the full run from `GET /runs/{run_id}` and renders the ideas in read-only mode using the same card layout as the Home page.
- [x] A "No history yet" message is shown if no saved runs exist.
- [x] A "Load more" button appears if more runs exist beyond the current page.

### Instructions

1. Create `pages/2_📋_History.py`.
2. Add `get_history(limit, offset)` and `get_run(run_id)` functions to `api_client.py`.
3. On page load, call `get_history` and render the results as a selectable list. Use the tech stack and formatted timestamp as the display label for each item.
4. When the user selects a run, store the selected `run_id` in `session_state` and call `get_run`. Render the ideas using the same card components used on the Home page. If the idea card component is duplicated, extract it into a shared `services/components.py` helper.
5. Track the current pagination offset in `session_state`. Show a "Load more" button if the number of returned items equals the page limit. Clicking it increments the offset and fetches the next page, appending results to the displayed list.

---

---

## DEVSTROM-V3-6 — Setup MCP Postgres Server (Standalone)

- [x] **Ticket completed**

**Type:** Infrastructure
**Priority:** Medium
**Depends on:** V3-3

### Description

MCP (Model Context Protocol) is an open standard published by Anthropic in 2024. It defines a structured protocol for LLM agents to interact with external systems — databases, APIs, file systems — using tool calls. Instead of Python code querying the database and injecting the result as a text string into a prompt, the LLM agent itself decides when to query and what to ask.

The official PostgreSQL MCP server (`@modelcontextprotocol/server-postgres`) is a pre-built Node.js process that sits between your agent and your database. It exposes SQL query capabilities as tools the agent can call. You configure it to connect to your database with read-only credentials and start it as a separate process.

This ticket is purely infrastructure: install the MCP server, configure it, verify it connects to the `devstrom` database, and confirm it can respond to a manual test query — all before any agent integration.

### Acceptance Criteria

- [ ] Node.js is installed on the server.
- [ ] `@modelcontextprotocol/server-postgres` is installed globally via npm.
- [ ] A dedicated read-only PostgreSQL user (`mcp_reader`) is created with SELECT-only access to the `runs` table.
- [ ] The MCP server starts successfully and connects to the `devstrom` database using the read-only credentials.
- [ ] A manual test query via the MCP protocol returns the expected rows from the database.
- [ ] A startup script at `scripts/start_mcp.sh` documents the command to start the server.
- [ ] `MCP_POSTGRES_URL` is documented in `.env.example` with the read-only connection string.

### Instructions

1. Install Node.js if not already present using the NodeSource package or the system package manager.
2. Install the MCP server globally using npm: `npm install -g @modelcontextprotocol/server-postgres`.
3. Connect to PostgreSQL as the admin user and create a new role named `mcp_reader` with a password. Grant `SELECT` on the `runs` table to this role. Confirm no other permissions are granted.
4. Create `scripts/start_mcp.sh` with the command to launch the MCP server using the `MCP_POSTGRES_URL` connection string. Make the script executable.
5. Run the script and confirm the server outputs a message indicating it is listening for connections and connected to the database without errors.
6. Send a test MCP protocol message (a JSON-RPC request) to the running server asking it to query the `runs` table. Confirm it returns a valid JSON response with the expected structure.
7. Add `MCP_POSTGRES_URL=postgresql://mcp_reader:password@localhost/devstrom` to `.env.example`.

---

---

## DEVSTROM-V3-7 — Integrate MCP into DeepAgent

- [x] **Ticket completed**

**Type:** Feature
**Priority:** Medium
**Depends on:** V3-6, V3-4

### Description

With the MCP server running from V3-6, this ticket wires it into the DeepAgent as a callable tool. The agent can then query the PostgreSQL database directly during the idea-generation step.

The key use case: before generating ideas, the agent can check whether the current user has had similar ideas generated in the past for the same tech stack. If prior ideas exist, the system prompt instructs the agent to ensure the new ideas are meaningfully different — different problems, different architectures, different primary focus. This makes the generator progressively more useful over time, rather than repeating the same ideas every session.

This integration is controlled by the `ENABLE_MCP` environment variable. When false, no tool is registered and behavior is identical to prior versions.

### Acceptance Criteria

- [ ] The MCP Postgres server from V3-6 is running before this ticket is tested.
- [ ] When `ENABLE_MCP=true`, an MCP tool is registered with the `generate_ideas` agent that allows it to execute read-only SQL queries against the `devstrom` database.
- [ ] The `_IDEAS_SYSTEM` prompt includes an instruction directing the agent to query the user's past runs for the same tech stack before generating new ideas, and to ensure the new ideas differ meaningfully from past results.
- [ ] `user_id` and `tech_stack` are included in the user message passed to the agent so it can construct the correct database query.
- [ ] Running two consecutive idea requests for the same tech stack produces a second set of ideas that is meaningfully different from the first.
- [ ] When `ENABLE_MCP=false`, no MCP tool is added and the agent behaves exactly as in prior versions.
- [ ] `ENABLE_MCP=false` is documented in `.env.example`.

### Instructions

1. Review the DeepAgents documentation for how to register an MCP server as a tool with `create_deep_agent`. Identify the correct parameter and configuration format.
2. In `_get_idea_agent()`, check the `ENABLE_MCP` environment variable. If true, create an MCP client instance configured to connect to the URL from `MCP_POSTGRES_URL` and pass it in the `tools` list when calling `create_deep_agent`.
3. Add a new section to the `_IDEAS_SYSTEM` prompt — after the existing guardrails — that instructs the agent to: call the database query tool to retrieve the current user's last three runs for the given tech stack; review any returned ideas; and ensure all new ideas are distinguishable by their core problem, architecture pattern, or primary use case.
4. In the `generate_ideas` node, include `user_id` and `tech_stack` in the user message string passed to the agent so it can form the SQL query independently.
5. Test by generating ideas for the same tech stack twice in a row. Inspect the second result and confirm the ideas are noticeably different from those in the first result.
6. Add `ENABLE_MCP=false` to `.env.example`.

---

*Last updated: 2026-02-25. Mark tickets done in the summary table above as you complete them.*
