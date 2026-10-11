The redaction happens after the API request has returned, in the background processing loop, not in the request handler.

**Trace**

1. **Route:** `POST /instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70-115`. It resolves the project and signal definition, then calls `signal_service.create_instance` and commits (`views.py:106-116`). `create_instance` in `src/dispatch/signal/service.py:650` copies the raw payload and strips non-serializable values, but does no redaction. The handler also takes a `background_tasks` parameter and never uses it. The raw payload is stored unredacted at this point.

2. **Processing loop:** `process_signals()` in `src/dispatch/cli.py:938` queries up to 500 `SignalInstance` rows with no `filter_action` and no `case_id`, oldest first. For each one it calls `signal_flows.signal_instance_create_flow` and commits (`cli.py:~1004`). `process_signal_batch` in `src/dispatch/signal/flows.py:385` does the same per ID. I didn't trace what calls `process_signal_batch`.

3. **Redaction:** `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46` begins with `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:59-60`), commented "before entities are extracted from the payload". This is the first thing the flow does after loading the instance.

4. **Redaction logic:** `src/dispatch/signal/redaction.py` returns a copy of `raw` with the value of every matching key replaced by `[REDACTED]`. Matching is case-insensitive, at any depth, and goes into dicts and lists. The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, which can be overridden by environment variable.

5. **Entity extraction:** Entity types are gathered and `entity_service.find_entities` runs against the already-redacted instance (`flows.py:62-75`). Entities are committed to the database there.

6. **Filtering:** `signal_service.filter_signal` runs after redaction and extraction (`flows.py:77-79`). A filtered instance returns early, but it has still been redacted. Canary and no-`create_case` instances also return after redaction.

7. **Case creation:** Only instances that survive the filter and have `create_case` set get a case created (`flows.py:~110` onward).

**Answers**

- Redaction is applied to the stored raw payload in the processing flow, before entity extraction and before the filter decision.
- Between the API response and the processing loop, the raw payload sits unredacted in the database. Anyone reading `SignalInstance.raw` in that window sees the secrets.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no