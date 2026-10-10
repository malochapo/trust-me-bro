#!/usr/bin/env bash
# sobre-dev: a local build of sobre, set up exactly like the sobre arm. `sobre init claude` (README "Connect agents"), then `sobre index build`
# (README: "build the indexes now rather than on first search") so the agent starts warm.
#
# init writes, into this HOME only:
#   $CLAUDE_CONFIG_DIR/.claude.json      mcpServers.sobre = {command: <abs path to sobre>}
#   $CLAUDE_CONFIG_DIR/settings.json     hooks: PostToolUse(.*) observe, PostToolUse(Bash) compress,
#                                        PostToolUse(Read) read-dedup, UserPromptSubmit/Stop/
#                                        PreCompact/SessionStart/SessionEnd observe
#   $CLAUDE_CONFIG_DIR/skills/sobre/SKILL.md
# Non-interactive init asks nothing, so the optional proxy stays off (it only works with
# API keys anyway; these runs use a subscription token).
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-dev"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
"$SOBRE" index build --root "$REPO" </dev/null >&2
assert_repo_clean
finish_setup '{}'
