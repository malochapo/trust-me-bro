Redaction is not done while the API request is handled. It happens later, in the background signal-processing flow, before entities are extracted.

**What happens to the instance**
1. `POST /instances` is handled by `create_signal_instance` in `signal/views.py:72`. It resolves the project and the signal definition (by external id or variant, else the default, else a 404). It then calls `signal_service.create_instance` and commits, so the instance is stored with the raw payload unredacted. The view never calls `signal_instance_create_flow` or `redact_raw`, and returns the instance.
2. A scheduled consumer picks the instance up later. `process_organization_signals` in `signal/flows.py` gets the unprocessed instance ids. `process_batch` (`process_signal_batch`) then calls `signal_instance_create_flow` for each id and commits.
3. `signal_instance_create_flow` (`signal/flows.py:46`) first runs `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
4. Next it gathers the entity types and calls `entity_service.find_entities`. Extraction therefore sees the redacted payload.
5. `signal_service.filter_signal` runs next. If a filter acts (snooze, deduplicate, etc.), the flow returns early and no new case is opened.
6. Otherwise the flow returns early for canary signals and for signals with `create_case` off. If neither applies, it goes on to create the case.

**Redaction function:** `redact_raw` in `signal/redaction.py`. It returns a copy of the payload with the value of every listed key replaced by `"[REDACTED]"`. Keys match case-insensitively, at any depth, inside dicts and lists.

**Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, overridable by environment variable, defaults to `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no