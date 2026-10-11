The API handler only stores the instance. Redaction runs later, in a background processing loop, so it does not happen while the request is handled.

**Trace**

1. **Request handling** (`src/dispatch/signal/views.py:70-113`, `create_signal_instance`). `POST /api/v1/{organization}/signals/instances` resolves the project and the signal definition, which is looked up by external id or variant, then the default. It calls `signal_service.create_instance` and commits. `create_instance` (`src/dispatch/signal/service.py:650`) persists `raw` as sent. Nothing is redacted, entities are not extracted, and no case is created. The handler never calls the flow, even though it accepts `background_tasks`.

2. **Processing** (`src/dispatch/signal/flows.py:385-400`, `process_signal_batch`). This runs from the scheduler's `main_processing_loop` (`flows.py:441`) and from a CLI command (`cli.py:1004`). It calls `signal_instance_create_flow` for each stored instance and commits after each one.

3. **`signal_instance_create_flow`** (`flows.py:46`):
   - Line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`. This comes before entity extraction, with the comment "mask sensitive values before entities are extracted from the payload".
   - Lines 63-75: entity types are gathered and `entity_service.find_entities` runs on the redacted payload.
   - Line 78: `signal_service.filter_signal` may filter the instance and return early.
   - Lines 102-107: canary signals and signals with `create_case` disabled stop here.
   - Later: case creation and identity engagement.

4. **Redaction** (`src/dispatch/signal/redaction.py`). `redact_raw` builds a set of lowercased field names and recursively copies dicts and lists. A dict key whose lowercased name is in the set has its value replaced with `[REDACTED]`. Matching is case-insensitive at any depth. Only keys are matched, not value contents. Other types pass through unchanged.

5. **Default keys** come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. The default is `password,secret,api_key,session_token,authorization`, and the env var overrides it.

**Consequences**

- The HTTP response and the initial database row contain the raw payload as sent, unredacted. The masking only reaches the stored `raw` once the background flow runs and commits.
- Redaction does run before entity extraction and filtering, so entities and filter rules never see the sensitive values.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no