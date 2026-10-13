#!/usr/bin/env bash
# sobre-rc2-mcp-always: sobre-rc2-mcp with its MCP server's tools loaded up front
# (`alwaysLoad: true`), so that the agent sees them in every request instead of finding them
# through tool search. Not a vendor setup: it asks whether agents left sobre's tools unused
# because they were deferred (docs/mcp-visibility.md).
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2"

cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
"$SOBRE" index build --root "$REPO" </dev/null >&2
assert_repo_clean
finish_setup '{}' always-load
