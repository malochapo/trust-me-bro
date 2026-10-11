Recap of the security review, covering the masking, the entity bug and the new test.

**Masking.** Sensitive values in the raw payload are masked in `redact_raw` (`src/dispatch/signal/redaction.py`). It replaces the value of any key whose lowercased name is in the configured set, at any depth in dicts and lists, with `[REDACTED]`. The default set is `password`, `secret`, `api_key`, `session_token` and `authorization`, set in `src/dispatch/config.py`. Matching is exact on the key name, so `apiKey` and `x-api-key` are not masked. The flow calls it in `signal_instance_create_flow` before entity extraction.

**Database exposure.** The unmasked payload is written to the database. `POST /signals/instances` commits the raw payload before any processing. The masked version is only written after the background loop processes the instance successfully, and a failed run rolls the masking back. If processing keeps failing, the unmasked payload stays in place.

**Entity bug.** Commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` now passes, 11 tests.

**Masked values as entities.** A JSONPath aimed at a masked field matched the `[REDACTED]` string, which then became an entity. Analysts reported unrelated instances grouped into one case through the deduplication filter. `find_entities` now masks its own copy of the payload and skips any match equal to the mask. I added `test_find_entities_never_extracts_masked_values`, which fails without the fix. Because `find_entities` is the single extraction point, the fix also covers entity-type creation and recalculation, which can read unprocessed raw. Payloads whose real value is the literal `[REDACTED]` are skipped as well.

**Status.** The changes are uncommitted in the working tree. I have not committed or pushed. `tests/entity` and `tests/signal` pass, 44 passed and 1 skipped.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95