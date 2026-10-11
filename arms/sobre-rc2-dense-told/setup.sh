#!/usr/bin/env bash
# sobre-rc2-dense-told: sobre-rc2-dense, with the user-level CLAUDE.md of the -told arms
# (lib-told.sh), which says when to use sobre's session tools and semantic search with
# mode="hybrid": rc.2 searches with BM25 unless a mode is given, embeddings or not.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-told.sh"
. "$(dirname "$0")/../lib-dense.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2-dense"

provision_dense "$SOBRE"
ORT=$(link_dense)
cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
ORT_DYLIB_PATH="$ORT" "$SOBRE" index build --root "$REPO" </dev/null >&2
write_told sobre-dense
assert_repo_clean
finish_setup "{\"ORT_DYLIB_PATH\": \"$ORT\"}"
