#!/usr/bin/env bash
# sobre-dev-fold3: sobre-dev-fold2 with the fold that keeps every value: only log lines that
# are the same but for their timestamp fold (signal lines never do), set up as sobre-rc2:
# `sobre init claude`, the hooks only.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-dev-fold3"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
[ ! -e "$CLAUDE_CONFIG_DIR/skills/sobre" ] || { echo "sobre init installed the skill without --mcp" >&2; exit 1; }
assert_repo_clean
finish_setup '{}'
