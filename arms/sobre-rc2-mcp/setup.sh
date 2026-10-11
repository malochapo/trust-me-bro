#!/usr/bin/env bash
# sobre-rc2-mcp: sobre 0.1.0-rc.2 with everything connected: `sobre init claude --mcp` (hooks,
# MCP server, skill), then `sobre index build` so the agent starts warm.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2"

cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
"$SOBRE" index build --root "$REPO" </dev/null >&2
assert_repo_clean
finish_setup '{}'
