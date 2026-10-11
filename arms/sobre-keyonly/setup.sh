#!/usr/bin/env bash
# sobre-keyonly: a control arm. Claude Code alone, exactly as the native arm, but billed
# to BENCH_KEY_SOBRE (an arm named sobre-<variant> bills to the sobre key). It tells
# whatever the key changes apart from what sobre changes.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
finish_setup '{}'
