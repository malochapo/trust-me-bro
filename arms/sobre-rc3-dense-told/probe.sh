#!/usr/bin/env bash
# sobre: what its usage ledger and session observer recorded during the run.
# Ledger: <data_dir>/usage.jsonl, data_dir = $XDG_DATA_HOME/sobre = $HOME/.local/share/sobre
# (rust/src/core/usage/mod.rs, core/data_dir.rs). One OTLP log record per line.
set -euo pipefail
python3 -I - "$HOME/.local/share/sobre" <<'PY'
import json, sys
from collections import Counter
from pathlib import Path
data = Path(sys.argv[1])

def attr(rec, key):
    for a in rec.get("attributes", []):
        if a.get("key") == key:
            return next(iter(a.get("value", {}).values()), None)

events, tools, records = Counter(), Counter(), 0
tokens_original = tokens_sent = 0
ledger = data / "usage.jsonl"
if ledger.exists():
    for line in ledger.read_text(errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        records += 1
        events[rec.get("eventName")] += 1
        if rec.get("eventName") == "sobre.compression":
            tools[f'{attr(rec, "sobre.surface")}:{attr(rec, "sobre.tool")}'] += 1
            tokens_original += int(attr(rec, "sobre.tokens.original") or 0)
            tokens_sent += int(attr(rec, "sobre.tokens.sent") or 0)

# The observer hook (SessionStart, UserPromptSubmit, ...) records the active transcript.
observer = data / "active_transcript.json"
observer_seen = observer.exists()
print(json.dumps({
    "active": records > 0 or observer_seen,
    "usage_records": records,
    "by_event": dict(events),
    "compressions_by_surface_tool": dict(tools),
    "tokens_original": tokens_original,
    "tokens_sent": tokens_sent,
    "observer_seen": observer_seen,
}, sort_keys=True))
PY
