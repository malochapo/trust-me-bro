#!/usr/bin/env bash
# native-told: plain Claude Code, with a user-level CLAUDE.md that asks it to keep what a later
# session needs in its own memory (lib-told.sh). The control for sobre-rc2-mcp-told.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
. "$(dirname "$0")/../lib-told.sh"
write_told native
finish_setup '{}'
