#!/usr/bin/env bash
# rtk: commands it ran (its tracking db, ~/.local/share/rtk/history.db) via `rtk gain`.
set -euo pipefail
gain=$(rtk gain --format json 2>/dev/null || echo '{}')
python3 -I - "$HOME/.local/share/rtk/history.db" "$gain" <<'PY'
import json, sqlite3, sys
from pathlib import Path
db, gain = Path(sys.argv[1]), json.loads(sys.argv[2] or "{}")
tables = {}
if db.exists():
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for (name,) in con.execute("select name from sqlite_master where type='table'"):
        tables[name] = con.execute(f'select count(*) from "{name}"').fetchone()[0]
summary = gain.get("summary", {})
commands = int(summary.get("total_commands") or tables.get("commands") or 0)
print(json.dumps({
    "active": commands > 0,
    "total_commands": commands,
    "tokens_input": summary.get("total_input"),
    "tokens_output": summary.get("total_output"),
    "tokens_saved": summary.get("total_saved"),
    "db_rows": tables,
}, sort_keys=True))
PY
