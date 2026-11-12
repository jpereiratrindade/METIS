#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env >/dev/null 2>&1
  set +a
fi
exec python3 scripts/metis_mcp.py "$@"
