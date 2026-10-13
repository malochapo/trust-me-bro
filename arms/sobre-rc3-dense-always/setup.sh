#!/usr/bin/env bash
# sobre-rc3-dense-always: sobre-rc3-dense with its MCP server's tools loaded up front
# (`alwaysLoad: true`), so that the agent sees them in every request instead of finding them
# through tool search. Not a vendor setup: it asks whether agents left sobre's tools unused
# because they were deferred (docs/mcp-visibility.md).
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-dense.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-rc3-dense"

provision_dense "$SOBRE"
ORT=$(link_dense)
cd "$HOME"
"$SOBRE" init claude --mcp </dev/null >&2
ORT_DYLIB_PATH="$ORT" "$SOBRE" index build --root "$REPO" </dev/null >&2
assert_repo_clean
finish_setup "{\"ORT_DYLIB_PATH\": \"$ORT\"}" always-load
