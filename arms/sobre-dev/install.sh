#!/usr/bin/env bash
# Installs a locally built sobre as the sobre-dev arm's binary, and prints its sha256 for
# arms/versions.json. Usage: arms/sobre-dev/install.sh <path to a built sobre binary>
set -euo pipefail
BENCH_TOOLS=${BENCH_TOOLS:-$HOME/.cache/trust-me-bro/tools}
install -D -m 0755 "$1" "$BENCH_TOOLS/bin/sobre-dev"
sha256sum "$BENCH_TOOLS/bin/sobre-dev"
