## Recap

**Flow.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`.
1. The view finds the signal definition, using the default one if needed, and returns 404 if none exists.
2. `signal_service.create_instance` builds the instance from the payload as sent and the view commits it. A duplicate id returns 409.
3. The API does not process the instance. The scheduler (or the CLI) picks up instances with no `filter_action` and no case, and runs `signal_instance_create_flow`.
4. That flow masks the payload with `redact_raw` (`flows.py:60`) and extracts entities.
5. `filter_signal` then applies snooze, dedup and filter rules. A filtered instance is stored and the flow stops. Canary instances and signals with `create_case` off are also stored and stop there.
6. Otherwise a case is created.

**Masking.** `redact_raw` replaces the value of any matching key with `"[REDACTED]"`. Matching is case-insensitive, at any depth, through dicts and lists. Only exact key names match, so `api-key` and `apiKey` are not masked. The defaults come from `SIGNAL_REDACTED_RAW_FIELDS` and can be overridden by environment variable.

**Unmasked in the database.** Yes. The API commits the raw payload before the flow masks it. The unmasked payload stays in the database until the scheduler or CLI processes the instance. If that never happens, it stays permanently. The API response is also built from the unmasked instance. `service.py:730-737` has an update path that stores the raw payload unmasked. I did not trace its callers.

**Entity extraction bugs.**
- **First-match bug:** commit `beb60cc4` sliced JSONPath matches to the first one. I removed the slice.
- **Dedup grouping bug:** extraction ran on masked payloads, so every session token became the entity `[REDACTED]` and unrelated instances were deduplicated together. `find_entities` now searches a redacted copy and skips masked values. A test covers both cases.

Neither fix is committed.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95