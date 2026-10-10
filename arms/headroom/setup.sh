#!/usr/bin/env bash
# headroom, proxy mode: `headroom proxy --port <port>` and ANTHROPIC_BASE_URL pointing at
# it (docs quickstart "Alternative: proxy mode"; proxy.mdx). Not `headroom wrap claude`:
# wrap also registers the Serena MCP server, a second tool that would confound the arm.
# ENABLE_TOOL_SEARCH=true: headroom's docs (troubleshooting.mdx, "Claude Code context
# window is larger through the proxy") tell manual proxy users to set it, since Claude
# Code turns tool search off for a custom ANTHROPIC_BASE_URL; `wrap` sets it too.
# Nothing is written into Claude Code's config. The proxy runs with its defaults
# (mode cache, savings profile coding, CCR on) until run.py kills $HOME/arm.pid.
set -euo pipefail
. "$(dirname "$0")/../lib.sh"

# Warm caches filled by install.sh (Kompress model, tiktoken vocabularies), so the proxy
# does not depend on downloads during the run.
mkdir -p "$HOME/.cache"
cache="$BENCH_TOOLS/cache/headroom"
[ -d "$cache/hf" ] && ln -sfn "$cache/hf" "$HOME/.cache/huggingface"
[ -n "$(ls -A "$cache/tiktoken" 2>/dev/null)" ] && export TIKTOKEN_CACHE_DIR="$cache/tiktoken"

port=$(python3 -I -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
cd "$HOME"
# setsid: the proxy leads its own process group, so run.py can stop it and its workers.
setsid "$BENCH_TOOLS/bin/headroom" proxy --port "$port" </dev/null >"$HOME/headroom-proxy.log" 2>&1 &
echo $! > "$HOME/arm.pid"
echo "$port" > "$HOME/arm.port"

# Ready means the proxy answers and Kompress (ONNX) has loaded: it warms in the
# background after startup, and requests before that pass through uncompressed.
if ! python3 -I - "$port" <<'PY'
import json, sys, time, urllib.request
url = f"http://127.0.0.1:{sys.argv[1]}/health"
deadline = time.time() + 180
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            health = json.load(r)
        if health.get("ready") and health["checks"]["kompress"].get("ready"):
            sys.exit(0)
    except (OSError, ValueError, KeyError):
        pass
    time.sleep(0.5)
sys.exit(1)
PY
then
  echo "headroom proxy (with Kompress) did not become ready on port $port" >&2
  tail -n 40 "$HOME/headroom-proxy.log" >&2
  exit 1
fi
assert_repo_clean
finish_setup "{\"ANTHROPIC_BASE_URL\": \"http://127.0.0.1:$port\", \"ENABLE_TOOL_SEARCH\": \"true\"}"
