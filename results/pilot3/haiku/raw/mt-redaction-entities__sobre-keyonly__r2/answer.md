## Recap

**Masking.** The payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:59-60`) before entity extraction and filtering. Matching is case-insensitive on exact key names, at any depth, inside dicts and lists. The default keys are set in `src/dispatch/config.py:98-102` and can be overridden with `SIGNAL_REDACTED_RAW_FIELDS`. I did not change the masking.

**Unmasked data in the database.** Yes. `POST /api/v1/{organization}/signals/instances` stores the raw payload unmasked and commits it in the request (`signal/service.py:create_instance`, `signal/views.py`). The response also returns it unmasked. Masking only happens later, in the processing flow. If that flow fails, the rollback discards the in-memory masking and the unmasked payload stays in the row, and the flow retries it. I found this by reading the code; I did not run the failure case.

**Entity extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`, so only the first match per entity type became an entity. I reverted that line. `tests/entity` passed afterward. I did not run the test against the broken code, so the link to the red CI comes from the diff.

**Masked values as entities.** This was a second bug. The flow masks the payload before entity extraction, so a JSONPath aimed at a masked key matched `"[REDACTED]"`. Every such instance got the same entity, and the dedup filter grouped them into one case. The fix is in `find_entities` (`src/dispatch/entity/service.py`). It matches against the redacted payload and skips any match equal to the mask. It covers the flow and the entity-type re-extraction path (`entity_type/service.py:95`). I added `test_find_entities_never_creates_entity_from_masked_value`. It fails without the fix and passes with it. `tests/signal`, `tests/entity`, and `tests/entity_type` pass: 50 passed, 1 skipped.

**Open items**
- The fixes are uncommitted in the working tree.
- The skip-on-mask rule also drops a payload value that is literally `"[REDACTED]"`. That is not a secret, so I accepted it.
- Not yet examined: `signal_service.update_instance` writes `raw` without masking. I found no callers in `src/`. The AWS plugin path (`plugins/dispatch_aws/plugin.py`) was not traced.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95