#!/usr/bin/env bash
# sobre-rc2-dense: the sobre 0.1.0-rc.2 build with local embeddings, everything connected:
# `sobre init claude --mcp`, the embedding model and ONNX Runtime (`sobre embeddings provision`,
# shared across runs, lib-dense.sh), then `sobre index build`, which builds the dense index too.
# ORT_DYLIB_PATH points sobre at the shared ONNX Runtime (a path variable, README).
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-dense.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc2-dense"

provision_dense "$SOBRE"
ORT=$(link_dense)
cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
ORT_DYLIB_PATH="$ORT" "$SOBRE" index build --root "$REPO" </dev/null >&2
assert_repo_clean
finish_setup "{\"ORT_DYLIB_PATH\": \"$ORT\"}"
