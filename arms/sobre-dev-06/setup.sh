#!/usr/bin/env bash
# sobre-dev-06: the sobre-dev arm with compression_level = 0.6 instead of the default 0.3.
# The setup is sobre-dev's, then one `sobre config set` (README "Configuration").
set -euo pipefail
"$(dirname "$0")/../sobre-dev/setup.sh" > "$HOME/.sobre-dev-setup.out"
"$BENCH_TOOLS/bin/sobre-dev" config set compression_level 0.6 </dev/null >&2
tail -n 1 "$HOME/.sobre-dev-setup.out"
rm -f "$HOME/.sobre-dev-setup.out"
