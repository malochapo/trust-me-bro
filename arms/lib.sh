# Shared helpers for arms/<arm>/setup.sh and probe.sh. Source it; do not run it.
#
# setup.sh runs with: HOME (fresh, empty), CLAUDE_CONFIG_DIR=$HOME/.claude, REPO (the
# task's checkout), BENCH_TOOLS, and a clean PATH. Its stdout must end with one JSON
# line: the extra environment the agent needs. Everything else goes to stderr.

: "${HOME:?}" "${CLAUDE_CONFIG_DIR:?}" "${BENCH_TOOLS:?}"

# Copy the MCP servers the tool registered in Claude Code's user config
# ($CLAUDE_CONFIG_DIR/.claude.json) into $HOME/mcp.json, the file run.py passes with
# --strict-mcp-config. Writes {"mcpServers":{}} when the tool registered none.
export_mcp() {
  python3 -I - "$CLAUDE_CONFIG_DIR/.claude.json" "$HOME/mcp.json" <<'PY'
import json, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
servers = {}
if src.exists():
    servers = json.loads(src.read_text() or "{}").get("mcpServers") or {}
dst.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n")
PY
}

# Leave the files run.py expects, then print the extra env as the last stdout line.
finish_setup() { # finish_setup '<json object of extra env>'
  mkdir -p "$CLAUDE_CONFIG_DIR"
  [ -f "$CLAUDE_CONFIG_DIR/settings.json" ] || echo '{}' > "$CLAUDE_CONFIG_DIR/settings.json"
  export_mcp
  echo "$1"
}

# Fail loudly if a setup step wrote into the task's checkout: the agent must start
# from the fixture exactly, whatever the arm.
assert_repo_clean() {
  local dirty
  dirty=$(git -C "$REPO" status --porcelain --ignored=no 2>/dev/null || true)
  if [ -n "$dirty" ]; then
    echo "setup wrote into the repo:" >&2; echo "$dirty" >&2; return 1
  fi
}
