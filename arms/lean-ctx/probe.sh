#!/usr/bin/env bash
# lean-ctx: its token counters (`lean-ctx stats json`) and its session observer.
set -euo pipefail
stats=$(lean-ctx stats json 2>/dev/null || echo '{}')
python3 -I - "$HOME/.local/share/lean-ctx" "$stats" <<'PY'
import json, sys
from pathlib import Path
data, stats = Path(sys.argv[1]), json.loads(sys.argv[2] or "{}")
commands = int(stats.get("total_commands") or 0)
radar = data / "context_radar.jsonl"
observer_seen = (data / "active_transcript.json").exists()
print(json.dumps({
    "active": commands > 0 or observer_seen,
    "total_commands": commands,
    "commands": {k: v.get("count") for k, v in (stats.get("commands") or {}).items()},
    "tokens_input": stats.get("total_input_tokens"),
    "tokens_output": stats.get("total_output_tokens"),
    "cep_sessions": (stats.get("cep") or {}).get("sessions"),
    "observer_seen": observer_seen,
    "radar_events": len(radar.read_text().splitlines()) if radar.exists() else 0,
}, sort_keys=True))
PY
