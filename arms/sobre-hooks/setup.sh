#!/usr/bin/env bash
# sobre-hooks: the sobre-dev build with its hooks only. `sobre init claude` as in the sobre-dev
# arm, then the MCP server entry and the skill are removed, so the agent's prompt carries
# nothing from sobre: this arm measures what the hooks save on their own (post-run Bash
# compression, Read dedup, the observer). No index is built: only the MCP tools use it.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"
SOBRE="$BENCH_TOOLS/bin/sobre-dev"

cd "$HOME"
"$SOBRE" init claude </dev/null >&2
python3 -I - "$CLAUDE_CONFIG_DIR/.claude.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
cfg = json.loads(p.read_text() or "{}")
servers = cfg.get("mcpServers") or {}
if "sobre" not in servers:
    sys.exit("sobre init registered no MCP server named sobre: " + ", ".join(servers))
del servers["sobre"]
p.write_text(json.dumps(cfg, indent=2) + "\n")
PY
[ -d "$CLAUDE_CONFIG_DIR/skills/sobre" ] || { echo "sobre init installed no skill" >&2; exit 1; }
rm -rf "$CLAUDE_CONFIG_DIR/skills/sobre"
assert_repo_clean
finish_setup '{}'
