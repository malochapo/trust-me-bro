Recap of the security review and the two fixes. Nothing is committed; the changes are in the working tree.

**Masking and the database.** The masking function is `redact_raw` in `src/dispatch/signal/redaction.py`. It masks values whose keys match, case-insensitively and at any depth, and replaces each with `"[REDACTED]"`. It runs once, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), before entity extraction and filtering. Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`. Masking is unchanged.

The unmasked payload is written to the database. `service.create_instance` stores `raw` as received, and the POST handler commits it before the background flow runs. The flow later overwrites `raw` with the masked copy, but the original stays in database history, WAL, and backups. The POST response also echoes the unmasked `raw` back to the caller.

**Entity extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, which kept only the first JSONPath match. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` went from 1 failed to 11 passed.

**Masked values grouping cases.** `"[REDACTED]"` is a string, so the JSONPath on the session token produced it as an entity. Every instance with a masked token then shared that entity value, and the deduplication filter grouped them into one case. `find_entities` now skips any match equal to `MASK`, so the guard covers the signal flow and the `entity_type` reprocessing paths. I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It fails with the guard removed and passes with it. `tests/entity`, `tests/signal`, and `tests/entity_type` give 50 passed, 1 skipped.

**Not fixed:** `src/dispatch/entity_type/flows.py` assigns `signal.entity_types.append(...)`, which returns `None`, so the block that follows never runs. This is unrelated to this change, so I left it alone.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95