## Security review recap

**Redaction (signal instances).** The POST handler (`src/dispatch/signal/views.py:70-129`) creates the instance and commits its `raw` payload without masking. Masking happens later, in the worker, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`). It replaces the value of any matching key with `[REDACTED]`, at any depth. Matching is case-insensitive on the key name only, so `x-api-key` or a secret inside a string value is not caught.

**Unmasked payload in the database.** Yes. The POST commit at `views.py:120` stores the raw payload before the worker runs. Once the worker masks and commits, the column holds the masked copy and the original is not kept. If the worker fails before its first commit, the unmasked payload stays in place and the row is retried.

**Entity extraction and masked values.** Two paths extracted entities from the raw payload:
- Processed instances: the masked `[REDACTED]` value became an entity. Every such instance got the same entity, so the dedup filter grouped unrelated instances.
- Entity type creation (`entity_type/service.py`): it extracted from stored payloads that could still be unmasked, so a real token could become an entity value.

**Fixes in the working tree (not committed):**
- `src/dispatch/entity/service.py`: `find_entities` now redacts the payload before matching and skips any match equal to `MASK`. Masking in `flows.py` is unchanged.
- `tests/entity/test_entity_service.py`: added `test_find_entities_never_extracts_masked_values`. It fails on the committed code and passes with the fix.
- Earlier, I reverted the first-match truncation in the same file, so the entity suite now passes.

**Test status:** `tests/entity` passes (12 passed) and `tests/signal` passes (32 passed, 1 skipped).

**Gaps and trade-offs:**
- No test covers `redact_raw` itself.
- The skip is by value, so a payload that literally contains `[REDACTED]` no longer produces an entity.
- Redaction matches key names exactly, so keys like `apiKey` or `auth_token` are not masked by default.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95