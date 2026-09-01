<p align="center">
  <img src="brand/banner.png" alt="Dev-Strom — You've learned the stack. Now build something with it." width="100%">
</p>

# Dev-Strom

**Get concrete project ideas for any tech stack, and analyze repositories with evidence-backed findings.**

- **The Idea Engine** — describe a stack or a goal in plain language; Dev-Strom pulls real-world problems from the live web and drafts project ideas, each with a problem statement, why it fits, real-world value, and an implementation plan. Expand any idea; export it as LLM-ready Markdown.
- **Repository Intelligence** — clone and parse a repo, then get an evidence-first analysis: findings with file/line citations, ranked recommendations, and an interactive architecture graph.

---

## Quick start

```bash
git clone git@github.com:vallaksa/Dev-strom.git
cd Dev-Strom
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # then set API_KEY
```

Run the API and the web UI in separate terminals:

```bash
uvicorn app.api:api --reload      # API on :8000
cd web && npm install && npm run dev   # UI on :5173 (proxies /api → :8000)
```

Open <http://localhost:5173>. Interactive API docs: <http://localhost:8000/docs>.

## Configuration

Set these in `.env`:

| Variable | Required | Description |
|---|---|---|
| `API_KEY` | Yes | LLM provider key (OpenAI-compatible, e.g. OpenRouter) |
| `TAVILY_API_KEY` | Recommended | Web-search fallback when Perplexity Sonar fails |
| `DATABASE_URL` | Yes | PostgreSQL connection string (see [Database](#database)) |

## API

All POST bodies are JSON (`-H 'content-type: application/json'`).

```bash
# Generate ideas — returns run_id + ideas
curl -sX POST localhost:8000/ideas \
  -d '{"intent": "Event-driven fintech backend with strong audit trails"}'

**Docs (when API is running):** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger), [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc).

---

## Architecture

### End-to-end flow (Ideas)

```

Past runs: `GET /history`, `GET /analyses`. Health: `GET /health`, `GET /ready`.

## Database

PostgreSQL with `pgvector`:

```bash
docker run -d --name devstrom-postgres -p 5432:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=devstrom -e POSTGRES_DB=devstrom \
  pgvector/pgvector:pg16
docker exec devstrom-postgres psql -U postgres -d devstrom -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

```
DATABASE_URL=postgresql://postgres:devstrom@localhost:5432/devstrom
```

## Docker

```bash
cp .env.example .env      # fill in API_KEY / TAVILY_API_KEY
docker compose up --build # db + one-shot migrate (alembic upgrade head) + api on :8000
```

Run the web dev server separately from `web/`.

## Testing

```bash
source .venv/bin/activate && pip install -r requirements-dev.txt
pytest            # hermetic — LLM, web search, and Postgres are mocked
ruff check .      # lint
mypy app          # types (advisory)
```

## Docs

- Architecture & roadmap — [docs/PLAN.md](docs/PLAN.md)
- Tickets — [docs/V3_TICKETS.md](docs/V3_TICKETS.md) · Deferred work — [docs/BACKLOG.md](docs/BACKLOG.md)
- Frontend — [web/README.md](web/README.md)
- PostgreSQL MCP (optional, lets the idea agent dedupe against past runs) — [postgresql-mcp](https://github.com/vallaksa/postgresql-mcp); set `MCP_HTTP_URL`, `MCP_API_KEY`, `ENABLE_MCP=true`
