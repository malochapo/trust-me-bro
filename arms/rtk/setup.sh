#!/usr/bin/env bash
# rtk: `rtk init -g` (README "Quick Start": "Claude Code / Copilot (default)"), with
# --auto-patch, the documented non-interactive form ("CI/CD") of answering "y" to the
# prompt that patches settings.json. Writes, into this HOME only:
#   $CLAUDE_CONFIG_DIR/settings.json   hooks.PreToolUse[Bash] = "rtk hook claude" (needs rtk on PATH)
#   $CLAUDE_CONFIG_DIR/RTK.md          short instructions, and "@RTK.md" in $CLAUDE_CONFIG_DIR/CLAUDE.md
#   ~/.config/rtk/filters.toml, ~/.local/share/rtk/history.db
# No MCP server. Telemetry is opt-in and init does not opt in when non-interactive.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"

cd "$HOME"
"$BENCH_TOOLS/bin/rtk" init -g --auto-patch </dev/null >&2
assert_repo_clean
finish_setup '{}'
