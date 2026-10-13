Five write routes have no `PermissionsDependency` in their route definition:

1. `src/dispatch/case/views.py:162`: `POST ""` (`create_case`)
2. `src/dispatch/case/views.py:236`: `POST /{case_id}/resources/conversation` (`create_case_channel`)
3. `src/dispatch/case/views.py:260`: `POST /{case_id}/resources` (`create_case_resources`)
4. `src/dispatch/incident/views.py:117`: `POST ""` (`create_incident`)
5. `src/dispatch/incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`)

I checked the route decorators only. The routers are plain `APIRouter()` instances, and I did not inspect the parent `authenticated_organization_api_router` in `src/dispatch/api.py`. No code was changed.

----- next turn -----

Only one of the five routes is a regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test that fails if it goes missing again.

**Finding:** Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message gives no reason for dropping it, and the sibling `PATCH` and `POST` custom-event routes still have the check.

The other two non-report routes never had a check, according to `git blame`, so I didn't count them as regressions:
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`) was added in `ced74f33` without a check.
- `POST /case/{case_id}/resources` (`create_case_resources`) was added in `f08a22b3` without a check.

Those two may still be worth a look, but that's a design or oversight question, not a removed check. The two open report routes (`POST` create case and `POST` create incident) are intentional, as you said.

**Changes:**
- `src/dispatch/incident/views.py:503`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_views.py` (new): looks up the route in `dispatch.incident.views.router` and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.

**Verification:**
- `python -m pytest tests/incident/test_incident_views.py`: passes with the fix.
- Same test with only the views change stashed: fails, so it catches the regression.
- `python -m pytest tests/case tests/incident tests/event`: 24 passed.

The test checks the route's declared dependencies rather than sending a request. That keeps it independent of auth fixtures, but it wouldn't catch a permission class that is declared and then bypassed in the handler.

----- next turn -----

The cases list showed restricted cases to members who were not participants. The cause is a missing participant check in the case visibility filter, and the fix is in `src/dispatch/database/service.py`.

**Cause:** `restricted_case_filter` (`src/dispatch/database/service.py:822`) let any restricted case through for any non-admin user. The restricted branch was not tied to a participant match:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # no participant check
IndividualContact.email == current_user.email,
```

The incident version does this correctly, pairing the restricted check with the participant check via `and_`.

**Introduced by:** commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). The refactor removed the `and_(...)` wrapper, and that changed the meaning of the filter.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping. I didn't change any tests.

**Verification:**
- `python -m pytest tests/database tests/case`: 40 passed with the fix.
- Same run on the unfixed code: `test_restricted_case_filter_with_test_data` fails, so the existing tests do catch this bug.

I did not run the cases list end to end as a member account. The check is verified at the query-filter level, not through the HTTP endpoint.

----- next turn -----



----- next turn -----

The payload is masked in memory by `redact_raw`, but the unmasked payload is written to the database during the POST, before masking happens.

**Path of a request**

1. **Route** `create_signal_instance` (`src/dispatch/signal/views.py:70`) resolves the project and signal definition, then calls `signal_service.create_instance` and commits (`views.py:~116`). This is the point where the raw payload is stored.
2. **Storage** `create_instance` (`src/dispatch/signal/service.py:650`) copies `raw` into the `SignalInstance` row as-is, only round-tripping it through JSON. Nothing is masked here. The `raw` column is `JSONB` (`src/dispatch/signal/models.py:239`).
3. **Background processing**: the route does not start the pipeline. A poller in `src/dispatch/cli.py` (~L960–1010) selects instances with `filter_action IS NULL` and `case_id IS NULL`, in batches of 500, and calls `signal_instance_create_flow` for each one, committing after each.
4. **Masking** `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction and before any filter or canary logic. The comment says this is deliberate.
5. **Entities**: `entity_service.find_entities` runs on the masked payload. JSONPath matching uses `signal_instance.raw` (`src/dispatch/entity/service.py:290`), so masked values cannot become entities.
6. **Filtering**: `signal_service.filter_signal` (`service.py:866`) applies snooze and deduplication, sets `filter_action` (`none` when nothing matched), and commits (`service.py:896`).
7. **Case creation**: if the instance is not filtered, not canary, and the definition has `create_case`, the flow creates a case (`flows.py:188`), links it (`flows.py:189`), and starts `case_new_create_flow` (`flows.py:203`).

**Where masking happens:** `src/dispatch/signal/redaction.py`.
- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` (`redaction.py:10`) returns a new structure. It normalizes the field names (strip, lowercase) and then calls `_redact`.
- `_redact` replaces the value of any dict key whose lowercased name is in the set with `"[REDACTED]"`, recursing into dicts and lists at any depth. Other values are returned unchanged.
- Matching is exact on the key name, not a substring match.

**Default keys** (`src/dispatch/config.py:98`, overridable by the `SIGNAL_REDACTED_RAW_FIELDS` env var, comma-separated):
`password`, `secret`, `api_key`, `session_token`, `authorization`

**Is the unmasked payload written to the database?** Yes, in one window.
- The POST route commits the raw payload unmasked (`signal/views.py` commit after `create_instance`). It is stored that way until the poller processes the instance.
- Once the flow runs, the masked version replaces it on the next commit. That commit is either the one inside the `if entity_types:` block (`flows.py:75`) or the one in `filter_signal` (`service.py:896`). Both come after `redact_raw`, so the masked version is what gets written in the normal path.
- If processing raises before a commit, `process_signal_batch` or the poller rolls back. The row then keeps the unmasked payload and will be masked again on the next attempt.
- So the unmasked payload persists in `signal_instance.raw` for as long as the instance is unprocessed, and the POST response returns it unmasked. That is the caller's own input, so this is not a new disclosure to that caller.

**Observations, not changed:**
- The default list is exact-match. Keys such as `apiKey`, `x-api-key` or `Api-Key` are not masked, and neither is `token`, which is not in the default list.
- No test file exercises `redact_raw` (`grep` found no references under `tests/`).
- The `raw` field is also read by the AI summary code (`src/dispatch/ai/service.py:317`). That is fine once processing has run, but it would see the unmasked payload for any instance that gets to the AI step without going through the flow.

I only read the code and did not run anything or change any files.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match for each entity type's JSONPath. I removed the slice, so every string match becomes an entity again.

Before the fix, `tests/entity/test_entity_service.py::test_find_entities_with_field_only` failed with `assert 1 == 2`. After the fix, `python -m pytest tests/entity` passes (11 passed). `python -m pytest tests/entity tests/signal` passes (43 passed, 1 skipped). I did not change any tests.

The commit's message says a JSONPath "names one field", but a JSONPath with wildcards or filters can match several fields. The slice dropped those matches silently. If the performance concern is still real, a fix would need to bound the work differently, not drop matches. I did not add that.

Nothing is committed. The working tree also still contains the earlier changes to `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, and the new `tests/incident/` test.

----- next turn -----

Masked values could still become entities because `find_entities` read the raw payload without masking it. The masking ran only in `signal_instance_create_flow`, so any other caller got the unmasked payload. The fix is now in `find_entities` itself.

**Why the instances grouped:** for the "GitHub: Personal access token exposed" signal, the session-token entity type's JSONPath matched the token field. Masking had already replaced that value with `"[REDACTED]"` in the flow, but extraction still produced an entity for it. Every instance then got an entity with the same value, `"[REDACTED]"`, and the deduplication filter on that entity type grouped them into one case. Extraction also ran from the database copy in `entity_type/service.py` and `entity_type/flows.py`, which for not-yet-processed instances still holds the unmasked payload.

**Fix** (`src/dispatch/entity/service.py`):
- `_find_entities_by_jsonpath_expression` now runs `redact_raw(signal_instance.raw)` before matching, so every caller gets masked input. `redact_raw` returns a copy, so the stored raw is not changed.
- Matches whose value is exactly `MASK` are skipped.
- Masking itself is unchanged (`src/dispatch/signal/redaction.py` and the call in `signal/flows.py`).

**Tests:** I added `tests/entity/test_entity_redaction.py`, with two tests:
- A masked session token, a masked nested `authorization` header, and an unmasked `user` field: only `alice` becomes an entity.
- `find_entities` does not modify `signal_instance.raw`.

The first test failed before the fix, which confirmed the leak. `python -m pytest tests/entity tests/signal` now gives 45 passed, 1 skipped. No existing tests were changed.

**Limits:**
- The skip is by value. A real field whose value is literally `"[REDACTED]"` (and is not a masked key) will also be skipped. I think that is acceptable, but say so if you want a key-path check instead.
- I did not run the GitHub signal end to end through the deduplication filter. The check is at the `find_entities` level.

Nothing is committed. The working tree also has the earlier changes to `database/service.py`, `incident/views.py`, `tests/incident/`, and now `entity/service.py` and `tests/entity/test_entity_redaction.py`.

----- next turn -----

Recap for the weekly report. Nothing is committed; all changes are in the working tree.

**1. Write routes without a permission check (case and incident APIs)**
- Five write routes had no `PermissionsDependency` on their route definition: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. I checked the route decorators only, not the parent `authenticated_organization_api_router` in `src/dispatch/api.py`, so a router-level check could still cover them.
- `create_case` and `create_incident` are the open report routes, which is intentional.
- `create_case_channel` and `create_case_resources` never had a check, per `git blame`. They are an open design question, and I left them unchanged.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed its `IncidentEventPermission` check, and the message gives no reason. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`. The test fails without the check. It inspects the declared dependencies, so it would not catch a check that is declared and then bypassed in the handler.

**2. Restricted cases visible to non-participants**
- The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) removed the `and_` that required a participant match for restricted cases. Any restricted case then passed for any non-admin user.
- I restored the grouping. `python -m pytest tests/database tests/case` gives 40 passed. The existing `test_restricted_case_filter_with_test_data` fails on the old code. I did not test the endpoint end to end as a member account.

**3. Masking of signal raw payloads**
- Masking is `redact_raw` in `src/dispatch/signal/redaction.py`, introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing", Sam Ortega, 2025-07-03). It runs in `signal_instance_create_flow` before entity extraction and filtering.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`. Matching is exact on the key name, case-insensitive.
- The unmasked payload is written to the database by the POST route, and stays there until the background poller processes the instance. After processing, the masked version is what gets committed. The POST response also returns the unmasked payload, which is the caller's own input.

**4. Entity extraction and the grouped "Personal access token exposed" instances**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) added `[:1]` to the JSONPath matches. Only the first match became an entity. I removed the slice. `tests/entity` went from 1 failed to 11 passed.
- A separate bug: `find_entities` extracted from the raw payload without masking it, so a masked token became an entity with the value `"[REDACTED]"`. Every instance then shared that entity, and the deduplication filter grouped them. The masking was done only in the signal flow, but other callers read the stored, still unmasked payload.
- Fix in `src/dispatch/entity/service.py`: extraction now runs on `redact_raw(signal_instance.raw)`, and matches equal to `"[REDACTED]"` are skipped. Masking is unchanged. I added `tests/entity/test_entity_redaction.py` (two tests). The first failed before the fix. `python -m pytest tests/entity tests/signal` gives 45 passed, 1 skipped.
- Limit: the skip is by value. A real field whose value is literally `"[REDACTED]"` is also skipped. I did not run the GitHub signal end to end through deduplication.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4