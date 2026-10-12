## Recap

**Investigation 1: unguarded write routes and the case visibility leak**

- **Unguarded write routes.** Four write handlers had no `PermissionsDependency` before my changes: `case.create_case` and `incident.create_incident` (open by design), plus `case.create_case_channel` and `case.create_case_resources`. The two case routes were never guarded, so neither is a regression.
- **Visibility leak.** Security reported that the cases list showed restricted cases to members who do not participate in them. The cause is `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc7cdb4d95cd7c7163b2d99763b98a8289` ("refactor(database): flatten the restricted case filter") was described as a refactor but dropped the participant check on restricted cases. I restored it. `test_restricted_case_filter_with_test_data` fails on the old filter and passes on the fix. `tests/database` and `tests/case`: 40 passed.

**Investigation 2: masking and signal instances**

- **Path of a signal instance.** `POST /signals/instances` stores the raw payload and commits it before any masking happens. A background loop then masks the payload, extracts entities, filters, and opens a case.
- **Masking.** `redact_raw` in `src/dispatch/signal/redaction.py` replaces the values of matching keys with `[REDACTED]`. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The masking was introduced in `d2675cf4b078246ae14df279469af513b348ab95` ("feat(signal): mask sensit…", 2025-07-03).
- **Unmasked payload in the database.** Yes. The POST route commits the unmasked payload, and it stays there until the loop reprocesses the instance.
- **Entity extraction bug.** Commit `beb60cc49435f38d6296e1607b07f6dff31804b1` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match list, so only one entity was created per entity type. I removed the slice. `tests/entity`: 11 passed.
- **Masked values as entities.** The signal's token entity type matched the `[REDACTED]` placeholder, so unrelated instances shared the entity `[REDACTED]` and were grouped into one case. The fix is in `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py`. It searches the masked payload and skips the `[REDACTED]` value. I added `test_find_entities_never_yields_masked_values`. It fails with the guard disabled and passes with it. `tests/entity`, `tests/entity_type`, `tests/signal`: 50 passed, 1 skipped.

**Open items**

- No code is committed. The working tree has changes in `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and `tests/entity/test_entity_service.py`.
- `python -m pytest` fails in this environment with `No module named 'slack_sdk'` from `tests/conftest.py`. All test runs used `python -c "import sys,pytest; sys.exit(pytest.main([...]))"`.
- The `create_case_channel` and `create_case_resources` routes are still unguarded. The gating change was offered but not requested, so I did not make it.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident
RESTORED: none (no regression found; the two case routes were never guarded, so no check was restored)
REMOVED_BY: none (no check was removed)
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95