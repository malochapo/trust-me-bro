The payload is redacted later, in a processing step that runs after the API request has returned, and then entities are extracted from the redacted copy.

**Trace**

1. **API handler:** `create_signal_instance` in `src/dispatch/signal/views.py:72` handles `POST /api/v1/{organization}/signals/instances`. It resolves the project and signal definition, then calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and commits. That service only strips `oncall_service` and does a JSON round-trip of `raw`. It does not redact. So the raw payload is stored unredacted at this point. The handler never calls the flow, and `background_tasks` is unused.
2. **Later processing:** A separate loop picks up unfiltered, uncased instances and calls `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`). The loop is in `src/dispatch/cli.py:~1004` and `src/dispatch/signal/flows.py:~394` (`process_signal_batch` / `process_organization_signals`).
3. **Redaction:** The first step of that flow is `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`), with the comment "mask sensitive values before entities are extracted from the payload".
4. **Entity extraction:** `entity_service.find_entities` runs after redaction (`flows.py:~65`), then `db_session.commit()`.
5. **Filtering:** `signal_service.filter_signal` runs next. If it filters the instance, the flow returns early. Otherwise it continues to case creation.

**Redaction function** (`src/dispatch/signal/redaction.py`)
- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` builds a case-insensitive set of field names and recurses through dicts and lists at any depth. Matching keys get the value `"[REDACTED]"`. It returns a new structure and does not mutate the input.
- The default list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. It is overridable through the environment variable of the same name.

**Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`

**Caveat:** Because the API commit persists `raw` before the flow runs, the unredacted payload is stored in the database until the processing step overwrites it. The redaction is therefore a post-ingest step, not a guarantee that secrets never reach storage. I did not check whether anything else reads `raw` between those two points, or whether the flow's later commit persists the redacted value (I assumed it does, since `raw` is reassigned on the ORM object).

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no