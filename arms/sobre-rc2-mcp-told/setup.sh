#!/usr/bin/env bash
# sobre-rc2-mcp-told: sobre-rc2-mcp, with a user-level CLAUDE.md that tells the agent when to use
# sobre's search and session tools (lib-told.sh). It measures the tools when they are used,
# not whether an agent finds them.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-told.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2"

cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
"$SOBRE" index build --root "$REPO" </dev/null >&2
write_told sobre
assert_repo_clean
finish_setup '{}'
