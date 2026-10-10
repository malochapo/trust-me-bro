#!/usr/bin/env bash
# lean-ctx: `lean-ctx init --agent claude` (docs/guides/claude-code.md "Quick Setup",
# README agent table), then `lean-ctx index build` (graph + BM25, docs/reference/
# 04-code-intelligence.md) so the agent starts warm.
# init runs from $HOME, which is not a git repository, so it skips its project files
# (AGENTS.md, LEAN-CTX.md, .claude/settings.local.json in the repo); with
# --setting-sources user Claude Code would not read them anyway.
# Writes, into this HOME only:
#   $CLAUDE_CONFIG_DIR/.claude.json   mcpServers.lean-ctx (alwaysLoad, autoApprove list)
#   $CLAUDE_CONFIG_DIR/settings.json  hooks: PreToolUse(Bash) rewrite, PreToolUse(Read|Grep|Glob...)
#                                     redirect, PostToolUse(.*) observe, PostToolUse(Read)
#                                     read-dedup, observe on SessionStart/UserPromptSubmit/Stop/
#                                     PreCompact/SessionEnd; permissions.allow mcp__lean-ctx__*;
#                                     permissions.deny Grep, Glob; statusLine
#   $CLAUDE_CONFIG_DIR/CLAUDE.md      lean-ctx block; skills/lean-ctx/SKILL.md; hooks/*.sh
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
LEAN="$BENCH_TOOLS/bin/lean-ctx"

cd "$HOME"
"$LEAN" init --agent claude </dev/null >&2
(cd "$REPO" && "$LEAN" index build </dev/null >&2)
assert_repo_clean
finish_setup '{}'
