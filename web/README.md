# Dev-Strom — Web (F3)

React frontend for Dev-Strom: idea generation, Repository Intelligence
(evidence-first repo analysis), and run history.

## Stack

- [Vite](https://vite.dev) + React + TypeScript
- [React Router](https://reactrouter.com) for client-side routing
- [`@xyflow/react`](https://reactflow.dev) (React Flow) + [`dagre`](https://github.com/dagrejs/dagre) for the architecture graph and its auto-layout
- [`mermaid`](https://mermaid.js.org) to render optional architecture diagrams

## Develop

```bash
npm install
npm run dev
```

This starts Vite's dev server (default `http://localhost:5173`). All `/api/*`
requests are proxied to `http://localhost:8000` — see `vite.config.ts` — which
strips the `/api` prefix, so `fetch("/api/ideas")` reaches the FastAPI
backend's `POST /ideas`. Run the backend separately (see the repo root
README) if you want to exercise the real API instead of demo mode.

## Build

```bash
npm run build
```

Runs `tsc -b` (typecheck) then `vite build`; output goes to `web/dist/`. This
is the acceptance gate for this feature — it must succeed with zero errors.

```bash
npm run preview   # serve the production build locally
```

## Demo mode

The backend may not be running wherever this is reviewed (missing
`API_KEY`/`TAVILY_API_KEY`, no Postgres, etc). **Demo mode** makes
every page — especially the Repository Intelligence graph — fully render and be
interactable using local fixtures instead of live API calls.

- **Runtime toggle**: the "Demo Mode" switch in the top nav bar. Persisted to
  `localStorage`, per-browser. This is the default way to explore the app
  without a backend.
- **Build-time flag**: set `VITE_DEMO_MODE=true` (see `.env.example`) to force
  demo mode on for every visitor — useful when deploying a backend-less
  preview build. When forced this way, the nav toggle is disabled (it can't
  be turned off).

Fixtures live in `src/fixtures/`:

- `projectGraph.ts` — a ~24-node ProjectGraph modeled on Dev-Strom's own
  backend (repo → packages → modules → classes/functions, external deps, a
  Postgres service node, and an entrypoint), with `contains` / `imports` /
  `calls` / `depends_on` / `reads_writes` / `exposes` edges.
- `analysis.ts` — a sample evidence-first `Analysis` with findings,
  recommendations, and the structural graph for the Repository Intelligence view.
- `ideas.ts` — sample ideas and history rows.

Each `src/api/*.ts` module checks `isDemoMode()` (`src/lib/demoMode.ts`) and
either returns the matching fixture (with a small artificial delay so
loading states are visible) or calls the real endpoint via `apiClient`.
Errors from the real API are surfaced through each page's loading/error
states regardless of demo mode.

## Project structure

```
src/
  api/          typed fetch client + one module per backend resource
                (ideas, analyze, history, health) + domain types
  components/   shared UI (AppShell, cards, badges, state blocks) and the
                graph/ subfolder (React Flow node/edge rendering, legend,
                detail panel, mermaid renderer)
  fixtures/     demo-mode sample data
  hooks/        useAsyncAction (on-demand calls), useAsyncData (load-on-
                mount), useDemoMode
  lib/          demoMode flag, dagre graph layout, mermaid render helper
  pages/        one file per route (Ideas, Repository Intelligence, History,
                AnalysisDetail, RunDetail)
  theme/        design tokens (tokens.css) + base styles/motifs (base.css)
```

This is intentionally modular so future scope (auth, settings, etc.) can add
new `pages/`, `api/`, and `hooks/` without restructuring what's here.

## Design system

A warm editorial "paper" aesthetic (in the spirit of october.dev), expressed
entirely as CSS custom properties in `src/theme/tokens.css` — colors,
fonts, spacing, and per-node/edge-type graph accents. Component CSS
consumes these tokens; nothing is hardcoded. Fonts (Inter, Fraunces,
JetBrains Mono) are loaded via a Google Fonts `@import` in `tokens.css`.

## Backend endpoints covered

`POST /ideas`, `POST /expand`, `POST /export`, `GET /history`,
`GET /runs/{run_id}`, `POST /analyze`, `GET /analyze/{run_id}`,
`GET /analyses`, `GET /health`, `GET /ready`. See `src/api/types.ts` for the
full typed contract.

## Known TODOs

- No auth yet; the API client has no place to attach credentials because the
  backend doesn't require any yet.
- The architecture graph re-runs dagre layout on every filter toggle; fine
  at fixture scale (~25 nodes) but worth memoizing/virtualizing for very
  large real repos.
