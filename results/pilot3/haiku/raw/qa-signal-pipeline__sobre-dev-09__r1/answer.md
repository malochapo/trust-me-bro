**Short answer:** The redaction is done by `dispatch.signal.redaction.redact_raw`, and it runs after the API request has returned, not inside it.

**Trace**

1. **API request.** `POST /api/v1/{organization}/signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project and signal definition, then calls `signal_service.create_instance` and commits. `create_instance` (`src/dispatch/signal/service.py:650`) stores `raw` as given, with only JSON round-tripping and the removal of `oncall_service`. Nothing is masked on this path. The handler accepts a `background_tasks` argument but never uses it.

2. **Background processing.** Nothing in the request path calls the signal flow. A separate worker does: `main_processing_loop` in `src/dispatch/signal/flows.py:440` (run by the `signals process` CLI command, `src/dispatch/cli.py:938`) iterates over organizations and processes unprocessed instances in batches. Each instance goes through `process_signal_batch` (`flows.py:385`) and then `signal_instance_create_flow` (`flows.py:46`).

3. **Redaction.** `signal_instance_create_flow` does `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before any entity extraction. The comment there says so explicitly. The redacted copy is saved by the batch's later commit.

4. **Entity extraction.** `entity_service.find_entities` runs on the redacted `raw` (`flows.py:65–75`).

5. **Filtering.** `signal_service.filter_signal` (`src/dispatch/signal/service.py:866`) runs next. If it returns true, the instance is filtered (deduplicated or otherwise) and the flow returns.

6. **Case creation.** Otherwise, canary instances are stored and returned, and instances whose signal has `create_case` false are stored and returned. Anything else proceeds to case creation.

**Redaction behavior**

- Keys are matched case-insensitively (`str(key).lower()`) at any depth, inside dicts and lists. Matching values are replaced with `[REDACTED]`.
- Matching is exact on the lowercased key. `apiKey` and `api-key` do not match `api_key`.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. It is an environment variable and can be overridden.

**Implication:** Between the API call and the processing loop picking up the instance, the unredacted payload is stored in the database. Redaction is not applied at ingestion.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no