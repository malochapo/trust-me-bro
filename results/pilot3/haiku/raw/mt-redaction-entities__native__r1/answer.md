## Security review recap

**Where masking happens.** The raw payload is masked in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), which calls `redact_raw` in `src/dispatch/signal/redaction.py`. The POST handler (`src/dispatch/signal/views.py`) does not mask anything. Masking runs in the background processing loop, after the request has returned.

**Default keys.** `password`, `secret`, `api_key`, `session_token`, `authorization` (`src/dispatch/config.py:98`, overridable with `SIGNAL_REDACTED_RAW_FIELDS`). Matching is case-insensitive on dict keys only, at any depth. Values are not scanned, so `apiKey` and `api-key` do not match `api_key`.

**Unmasked data in the database.** Yes. `create_instance` stores the raw payload as received, and the POST commits it before masking runs. The masked version overwrites it only in a later commit during processing. If processing fails before its first commit, the rollback discards the masking and the row keeps the unmasked payload. Until processing runs, `GET /instances` also returns it.

**Extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, so only the first match became an entity. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` went from 1 failing to 11 passing.

**Grouping bug.** Masking replaces the value with the string `"[REDACTED]"`, and extraction treated that string as a normal value. Every instance then shared one `"[REDACTED]"` entity, and dedup grouped them. `find_entities` now searches the redacted payload and skips any match equal to `MASK`. Masking itself is unchanged. I added `test_find_entities_skips_masked_values`, which fails without the check and passes with it. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Open items**
- The fixes are uncommitted in the working tree. The grouping fix and the extraction revert both touch `src/dispatch/entity/service.py`.
- The skip compares by value, so a literal `"[REDACTED]"` in a payload is also skipped.
- The full test suite was not run.
- Unmasked payloads still sit in the database until processing runs. Moving masking into the POST path would close that window, but I have not changed it.

```
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95
```