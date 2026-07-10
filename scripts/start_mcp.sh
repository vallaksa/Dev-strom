#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_ROOT="${POSTGRESQL_MCP_ROOT:-$ROOT/../postgresql-mcp}"

if [[ -z "${MCP_POSTGRES_URL:-}" ]]; then
  echo "Missing MCP_POSTGRES_URL. Set it (or export it) before starting MCP." >&2
  exit 1
fi

if [[ -x "$MCP_ROOT/scripts/start.sh" ]]; then
  exec env DATABASE_URL="$MCP_POSTGRES_URL" "$MCP_ROOT/scripts/start.sh"
fi

if [[ -f "$MCP_ROOT/dist/index.js" ]]; then
  exec node "$MCP_ROOT/dist/index.js" "$MCP_POSTGRES_URL"
fi

echo "postgresql-mcp not found at $MCP_ROOT. Clone/build it or set POSTGRESQL_MCP_ROOT." >&2
exit 1
