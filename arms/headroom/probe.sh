#!/usr/bin/env bash
# headroom: the running proxy's /stats (run.py probes before it stops the proxy).
set -euo pipefail
# Also: Kompress's state from /health, and the code-aware line of the startup log.
python3 -I - "$(cat "$HOME/arm.port" 2>/dev/null || echo 0)" "$HOME/headroom-proxy.log" <<'PY'
import json, re, sys, urllib.request
from pathlib import Path
port, log = sys.argv[1], Path(sys.argv[2])
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/stats", timeout=10) as r:
        stats = json.load(r)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=10) as r:
        kompress = json.load(r).get("checks", {}).get("kompress", {})
except (OSError, ValueError) as e:
    print(json.dumps({"active": False, "error": f"no /stats on port {port}: {e}"}))
    sys.exit(0)
m = re.search(r"Code-Aware:\s+(\w+)", log.read_text(errors="replace")) if log.exists() else None
summary = stats.get("summary", {})
comp = summary.get("compression", {})
requests = int(summary.get("api_requests") or 0)
print(json.dumps({
    "kompress": {k: kompress.get(k) for k in ("ready", "status", "backend")},
    "code_aware": m.group(1) if m else None,
    "active": requests > 0,
    "api_requests": requests,
    "requests_compressed": comp.get("requests_compressed"),
    "tokens_removed": comp.get("total_tokens_removed"),
    "tokens_before": comp.get("total_tokens_before"),
    "primary_model": summary.get("primary_model"),
}, sort_keys=True))
PY
