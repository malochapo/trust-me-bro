#!/usr/bin/env bash
# sobre-rc3-dense-told: sobre-rc3-dense with the user-level CLAUDE.md of sobre-rc2-mcp-told
# (lib-told.sh). Otherwise as sobre-rc3-dense: the sobre 0.1.0-rc.3 build with local embeddings, everything connected:
# `sobre init claude --mcp`, the embedding model and ONNX Runtime (`sobre embeddings provision`,
# shared across runs, lib-dense.sh), then `sobre index build`, which builds the dense index too.
# From rc.3, semantic search ranks by hybrid by default once the model is installed.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-dense.sh"
. "$(dirname "$0")/../lib-told.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc3-dense"

provision_dense "$SOBRE"
ORT=$(link_dense)
cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
ORT_DYLIB_PATH="$ORT" "$SOBRE" index build --root "$REPO" </dev/null >&2
write_told sobre
assert_repo_clean
finish_setup "{\"ORT_DYLIB_PATH\": \"$ORT\"}"
