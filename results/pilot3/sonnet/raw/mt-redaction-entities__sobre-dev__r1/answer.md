## Recap

**Flow.** `POST /signals/instances` handles the request in `create_signal_instance` (`signal/views.py`). `create_instance` (`signal/service.py`) writes the payload to the database and the view commits it. The view doesn't run the processing flow. A worker later picks up unprocessed instances through `main_processing_loop` or the `cli.py` loop, and runs `signal_instance_create_flow`. That flow does the following:
- It masks `raw` with `redact_raw`.
- It extracts entities with `find_entities`.
- It applies the filters in `filter_signal`. A filtered instance is deduplicated or snoozed and gets no new case.
- Otherwise it creates a case, unless the signal is a canary or has `create_case` off.

**Masking.** `redact_raw` replaces the value of any key named in `SIGNAL_REDACTED_RAW_FIELDS` with `"[REDACTED]"`. Matching is by exact key name, case-insensitive, at any depth in dicts and lists. The environment variable `SIGNAL_REDACTED_RAW_FIELDS` overrides the defaults.

**Gap.** The unmasked payload is committed to the JSONB `raw` column at ingestion, before the worker masks it. The `GET /signals/instances` endpoint and the POST response both return it unmasked, and it stays that way until the worker commits the masked copy. The second creation path, `signal_service.create_signal_instance`, also doesn't mask. I proposed masking in `create_instance` but haven't made that change.

**Bugs found this session:**
- **First-match-only extraction:** commit `beb60cc4` truncated JSONPath matches with `[:1]`. I reverted that line and `tests/entity` passes.
- **Masked values becoming entities:** masking ran before extraction, so a JSONPath on `session_token` gave every instance the entity `"[REDACTED]"`, and deduplication grouped unrelated instances. `find_entities` now skips values equal to the mask. I added `test_find_entities_skips_masked_values`, and `tests/entity` and `tests/signal` pass.
- Both fixes are in the working tree and not committed.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95