#!/usr/bin/env bash
# sobre-dev-09b: the sobre-dev setup with a later build of sobre (installed as
# $BENCH_TOOLS/bin/sobre-dev-b) and compression_level = 0.9. That build never cuts
# diffs, blame, search results or listings short at 0.9 (sobre-ai 935756b6b).
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-dev-b"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
"$SOBRE" index build --root "$REPO" </dev/null >&2
"$SOBRE" config set compression_level 0.9 </dev/null >&2
assert_repo_clean
finish_setup '{}'
