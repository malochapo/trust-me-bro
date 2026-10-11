#!/usr/bin/env bash
# sobre-rc2: sobre 0.1.0-rc.2 as released, set up as its README says: `sobre init claude`. Since
# rc.2 that connects the hooks only (post-run Bash compression, Read dedup, the observer): the
# MCP server and the skill are opt-in, and a non-interactive init does not ask.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
[ ! -e "$CLAUDE_CONFIG_DIR/skills/sobre" ] || { echo "sobre init installed the skill without --mcp" >&2; exit 1; }
assert_repo_clean
finish_setup '{}'
