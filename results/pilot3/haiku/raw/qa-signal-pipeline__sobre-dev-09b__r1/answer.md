**Short answer:** Redaction happens in `signal_instance_create_flow`, not in the API handler. It runs after the request has returned, in the background processing job. Until then the raw payload is stored unredacted.

**Trace**

1. **API handler, `src/dispatch/signal/views.py:72` (`create_signal_instance`).** It resolves the project and the signal definition (by external id or variant, falling back to the default). It then calls `signal_service.create_instance` and commits. The handler never calls the flow, and it does not redact. Its `background_tasks` parameter is declared but not used. The request ends with the raw payload stored as sent.

2. **Service, `src/dispatch/signal/service.py:650` (`create_instance`).** It copies `raw`, drops `oncall_service` if present, and writes the `SignalInstance` row. No masking here.

3. **Processing, `src/dispatch/signal/flows.py`.** The job `process_signals_for_organization` (around line 405) fetches unprocessed instance IDs and passes them in batches to `process_signal_batch` (line 385). That calls `signal_instance_create_flow` (line 46). The CLI command `process_signals` (`src/dispatch/cli.py:938`) drives this. I did not trace what triggers that command.

4. **Inside `signal_instance_create_flow`.** The first step is at line 60:
   ```python
   signal_instance.raw = redact_raw(signal_instance.raw)
   ```
   This is before entity extraction (`entity_service.find_entities`, around line 70). Afterwards it runs `filter_signal`. Entities are extracted from the masked payload, and a filtered instance stops there. I did not verify where the case is opened; I only confirmed the order of the redaction, entity extraction and filter steps.

**Redaction details**

- `redact_raw` in `src/dispatch/signal/redaction.py` returns a copy. It masks each value whose key matches a configured name, case-insensitively, at any depth inside dicts and lists. Matching is on the whole key, not a substring. The mask is `[REDACTED]`.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. The environment variable replaces the list.
- Because `db_session.commit()` runs after entity extraction, the masked `raw` is what gets persisted. The unredacted payload is stored in the database between API receipt and processing.

**Answers**

- Redaction function: `redact_raw`, called from `signal_instance_create_flow`.
- Default keys: `password, secret, api_key, session_token, authorization`.
- Before entity extraction: yes.
- During the API request: no.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no