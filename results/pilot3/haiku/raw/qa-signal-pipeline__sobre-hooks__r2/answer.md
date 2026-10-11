Redaction runs in the background worker, not during the API request. The POST handler only stores the raw payload, and the flow that masks it runs later.

**Trace**

1. **`POST /api/v1/{organization}/signals/instances`** → `create_signal_instance` in `src/dispatch/signal/views.py:72`. It resolves the project and signal definition, then calls `signal_service.create_instance`.
2. **`signal_service.create_instance`** (`src/dispatch/signal/service.py:650`) builds the `SignalInstance` row and stores `raw` as a JSON round-trip of the submitted payload. It does not redact. The view commits and returns this object, so the response and the stored row both hold the raw payload as submitted. The `background_tasks` parameter is declared but never used.
3. **Processing happens later.** The `process_signals` command (`src/dispatch/cli.py:938`) is a separate worker. It polls `get_unprocessed_signal_instance_ids` (`signal/service.py:900`), and for each instance calls `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`). I did not trace exactly how `main_processing_loop` is started from the CLI. The `process_signals` command is the only entry point I found for it.
4. **Redaction** happens in that flow, at `flows.py:60`: `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment says it runs before entity extraction.
5. **`redact_raw`** (`src/dispatch/signal/redaction.py:10`) returns a copy with matching keys replaced by `[REDACTED]`. Matching is case-insensitive, exact on the key name (not substring), and applies at any depth inside dicts and lists. It delegates to the recursive helper `_redact`.
6. **Default keys** come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`, which is overridable through that environment variable. The default is `password,secret,api_key,session_token,authorization`.
7. **Entity extraction** follows at `flows.py:66–76`, so extraction sees the masked payload.
8. **Filtering** comes next: `signal_service.filter_signal` (`service.py:866`) can drop the instance (snooze or dedup), and the flow returns early. Otherwise the flow applies canary and `create_case` checks and creates a case, linking it to the instance.

**Implication:** the unredacted payload is stored in the database and returned by the POST response until the worker runs. I did not check whether anything else in the API path strips it. The redaction only protects data after the worker has processed the instance.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no