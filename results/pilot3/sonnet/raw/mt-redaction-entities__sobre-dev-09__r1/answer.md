## Recap

**Request path.** `POST /api/v1/{organization}/signals/instances` (`create_signal_instance`, `signal/views.py:70`) finds the signal definition. It calls `signal_service.create_instance`, then commits and returns. A worker later runs `signal_instance_create_flow` (`signal/flows.py:46`) on instances that have no `filter_action` and no `case_id`. The flow does the following:
- It masks `raw` with `redact_raw`.
- It extracts entities.
- It applies filters (snooze, dedup).
- It either returns, for filtered or canary instances and signals that don't create cases, or creates a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of each matching key with `[REDACTED]`. Matching is on the exact key name, case-insensitive, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` setting can override them. Keys like `client_secret` or `apiKey` are not masked.

**Unmasked data is stored.** The API commit in `views.py` persists the original `raw`, and so does the scheduler path (`create_signal_instance` in `signal/flows.py`). Redaction only happens later in the worker. Secrets sit in plaintext in the database until then, and they are also returned in the API response. The suggested fix is to redact inside `signal_service.create_instance`. I haven't made that change.

**Entity extraction regression.** Commit `beb60cc4` added `[:1]` to the JSONPath `find` call in `entity/service.py`, so only the first match became an entity. I reverted that line, and `tests/entity` passes again.

**Masked values becoming entities.** Masking runs before extraction, so a masked session token became the entity `[REDACTED]` on every instance. The dedup filter then grouped unrelated GitHub token instances into one case. `find_entities` now skips values equal to `[REDACTED]`. I added `test_find_entities_skips_masked_values`, and `tests/entity` plus `tests/signal` give 44 passed and 1 skipped. The fixes are uncommitted.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4