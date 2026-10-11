#!/usr/bin/env bash
# sobre-dev-fold2: a development build of sobre with the second log fold (signal lines never
# fold; routine lines fold in runs of 6+ or when a template repeats 8+ times, interleaved or not;
# more log formats), set up as sobre-rc2: `sobre init claude`, the hooks only.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-dev-fold2"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
[ ! -e "$CLAUDE_CONFIG_DIR/skills/sobre" ] || { echo "sobre init installed the skill without --mcp" >&2; exit 1; }
assert_repo_clean
finish_setup '{}'
