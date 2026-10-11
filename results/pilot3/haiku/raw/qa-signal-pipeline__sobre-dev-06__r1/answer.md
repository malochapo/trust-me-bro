The redaction happens after the API request has returned, in a background processing step, not in the request handler.

**Request path (synchronous)**

1. `create_signal_instance` in `src/dispatch/signal/views.py:70` handles `POST /api/v1/{organization}/signals/instances`. It resolves the project and signal definition, then calls `signal_service.create_instance`.
2. `create_instance` in `src/dispatch/signal/service.py:650` copies `raw`, JSON round-trips it, builds a `SignalInstance`, and calls `db_session.add`. It does not redact. The handler then commits and returns the instance (`views.py:~113`). So the stored `raw` is the unredacted payload at this point.

**Background processing (asynchronous)**

3. `main_processing_loop` (`src/dispatch/signal/flows.py:441`) → `process_organization_signals` (`flows.py:406`) picks up unprocessed instance IDs and calls `process_signal_batch` (`flows.py:385`).
4. `process_signal_batch` calls `signal_instance_create_flow` (`flows.py:46`) and commits after each instance.
5. In that flow, line 60 runs `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment says it masks values "before entities are extracted from the payload."
6. Only after that does it run entity extraction (`entity_service.find_entities`, `flows.py:69`) and then `signal_service.filter_signal` (`flows.py:78`), which decides whether the instance is filtered. I did not trace the case-creation branch beyond that point.

**Redaction function**

- `redact_raw` in `src/dispatch/signal/redaction.py` returns a copy with the value of each matching key replaced by `[REDACTED]`. Matching is case-insensitive on exact key names, at any depth through dicts and lists. It is not substring matching.
- The default key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`. It can be overridden by that environment variable.

**Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`

**Caveat:** because redaction runs later, the unredacted `raw` is written to the database during the request. It is only replaced with the masked copy when the flow runs and its batch commits. Anything that reads `raw` before that point sees the original values.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no