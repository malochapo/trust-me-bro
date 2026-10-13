Four mutating routes in the two files have no `PermissionsDependency` in their route definition:

1. `src/dispatch/case/views.py:162`: `POST ""`, `create_case`
2. `src/dispatch/case/views.py:236`: `POST /{case_id}/resources/conversation`, `create_case_channel`
3. `src/dispatch/case/views.py:260`: `POST /{case_id}/resources`, `create_case_resources`
4. `src/dispatch/incident/views.py:117`: `POST ""`, `create_incident`
5. `src/dispatch/incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}`, `delete_custom_event`

That makes five, not four. I've listed the five above.

This covers the route decorators in each file. Neither `APIRouter()` call declares router-level dependencies. I only checked how the routers are mounted in `src/dispatch/api.py` for the route-level question; I did not check whether those mount points add any permission checks. No code was changed.

----- next turn -----

The regression was in the incident delete-event route, and it's restored. The new test fails without the check and passes with it.

**The regression:** `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) lost its `PermissionsDependency([IncidentEventPermission])` in commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14). That commit was a one-line deletion, and nothing in its message mentions permissions. The case equivalent still checks `CaseEventPermission`, so the incident route was the odd one out.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the delete route. This is the only change to existing code.
- `tests/incident/test_incident_views_permissions.py` (new): finds the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its declared permission classes. I wrote it as a structural check rather than an HTTP call because it needs no auth fixtures and fails on exactly the missing declaration.

**Verification:** I ran the new test with `python -m pytest`. With the line removed it failed, and with it restored it passed. `tests/case/test_case_event_views.py` also passes. I did not run the full suite.

**Not regressions:**
- `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources` were added without a permission check in `ced74f33` and `f08a22b3`. Nothing was removed, so I left them alone. They may still deserve a check, but that's a gap rather than a regression.
- `POST ""` on case and incident are the open-reporting routes you described.

----- next turn -----

The cause is fixed. The cases list was showing restricted cases to people who aren't participants, and it came from `42699ebc`.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` (around line 836) let any restricted case through for every non-admin user. The participant-email check was supposed to apply only to restricted cases, but the refactor split it into separate top-level `or_` terms, so the email check no longer applied to them.

**Commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It undid the `and_` added by the security fix `b05613b5` (#6155, Marc Vilanova). The refactor's message says nothing about a behaviour change.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching the incident filter. This is the only change to that file.

**Verification:**
- `tests/database/test_service.py` and `tests/case/test_case_service.py`: 35 passed with the fix.
- Without the fix, `test_restricted_case_filter_with_test_data` fails and the other 34 pass. So the existing test already catches this bug; I didn't change or add any tests.

The earlier incident-view change from the previous task is still in the working tree, so `git diff` shows both files.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in `redact_raw` (`src/dispatch/signal/redaction.py:10`), but it runs in the background processing flow, not in the POST handler. The POST handler writes the unmasked payload to the database and commits it. The masked version only overwrites that row later, if processing reaches the commit.

**Path from the POST to a case or a filter**

1. **`create_signal_instance`** (`src/dispatch/signal/views.py:70-125`) resolves the signal definition by `externalId`/`variant` or falls back to the default. It calls `signal_service.create_instance` and then `db_session.commit()`. The response is returned here, and no flow runs in this request.

2. **`create_instance`** (`src/dispatch/signal/service.py:650-`) builds the `SignalInstance` from `raw` as-is. The JSON round-trip only makes dates serializable and does not mask anything. **The unmasked payload is committed to the database at this point.**

3. **Processing** happens later, in the `signals process` loop (`src/dispatch/cli.py:937`). Each cycle selects up to 500 instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, and calls `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) for each one. The loop commits after each instance.

4. **`signal_instance_create_flow`** loads the instance and, as its first step on the payload, runs `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`). Only after that does it:
   - extract entities from `raw` (`entity_service.find_entities`, which therefore sees only masked values);
   - run `filter_signal` (snooze, deduplication, and filter rules), which can end the flow with a `filter_action`;
   - return early for canary instances or signal definitions with `create_case` disabled;
   - otherwise create or attach a case.

**Where masking happens and what it masks**

- Function: `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`, which calls the recursive `_redact`. Key names are lowercased and stripped, and matching is case-insensitive. Matching applies at any depth inside dicts and lists. The matched value is replaced with `"[REDACTED]"`. Only dict keys are matched; string values are not scanned.
- Default keys (`src/dispatch/config.py:98-102`, overridable with the `SIGNAL_REDACTED_RAW_FIELDS` env var): `password`, `secret`, `api_key`, `session_token`, `authorization`.

**Is the unmasked payload written to the database?** Yes, in two cases:

- **Between the POST and processing.** `create_instance` commits the raw payload unmasked, and that row stays unmasked until the flow runs. If the `signals process` loop is not running, the value stays in the table.
- **If the flow fails before its commit.** The redaction is only in memory until a commit happens. `find_entities` commits only when entity types exist, and the loop commits after a successful instance. If the flow raises, that instance's raw stays unmasked in the database and is retried on the next cycle.

When the flow succeeds, the redacted `raw` is committed, so the row ends up masked. The raw column holds unmasked secrets only for the window described above.

**Other things to know**

- The POST response returns the unmasked `raw` to the caller, since `SignalInstanceBase.raw` is not masked. That is the sender's own data, but it does mean the same value is returned in the HTTP response.
- Secrets in string values, such as a JSON string inside a field, or in keys with other names, are not masked by default.
- I did not run anything or change code. The trace is from reading the code and the `create_instance` tail at `service.py:690-737`. I did not confirm the timing of the loop in a running deployment.

----- next turn -----

The entity extraction regression came from `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega). It added a `[:1]` slice to the JSONPath matches in `find_entities` (`src/dispatch/entity/service.py:289`), so only the first matching field became an entity. I reverted that line to `matches = jpath.find(signal_instance.raw)`, which is the code before the commit.

`python -m pytest tests/entity` now passes: 11 passed. The one failure before the fix was `test_find_entities_with_field_only`, which expected 2 entities and got 1. I did not change any tests.

The working tree still has the earlier changes from the previous two tasks (`src/dispatch/database/service.py`, `src/dispatch/incident/views.py`), so `git diff` shows those too. I only ran the `tests/entity` suite, not the full test suite.

----- next turn -----

The cause is that a masked value could become an entity. The flow masks `raw` before it calls `find_entities`, so a JSONPath aimed at the session token read `"[REDACTED]"` and created an entity with that value. Every instance then shared that one entity, and deduplication grouped them into one case.

**Fix** (`src/dispatch/entity/service.py`): `find_entities` now masks the payload itself, using `redact_raw`, before it runs the JSONPath matches. It also skips any string equal to `MASK`. The masking is unchanged; this covers every caller, including `entity_type/flows.py` and `entity_type/service.py`, which run on payloads the flow has not masked yet.

**Test** (new file `tests/entity/test_entity_redaction.py`): it checks that an unmasked session token, an unmasked nested `authorization` value, and an already-masked `"[REDACTED]"` value produce no entities, and that an unrelated field such as `user.name` still produces one. I did not change any existing test.

**Verification:**
- `python -m pytest tests/entity tests/signal`: 44 passed, 1 skipped.
- With the fix stashed, the new test fails, so it catches the regression.

The working tree still has the earlier changes from the previous tasks. I did not run the full test suite.

----- next turn -----

## Weekly recap

**1. Unprotected mutating routes (security review)**
- Five data-changing handlers had no `PermissionsDependency` at the start: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open on purpose. The other three are not.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if it goes missing again.
- `case.create_case_channel` and `case.create_case_resources` have had no check since they were added (`ced74f33`, `f08a22b3`). I reported them as gaps and did not change them.

**2. Cases list showing restricted cases to non-participants**
- Cause: `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` grouping, so any restricted case matched for any user.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"). The correct version came from `b05613b5` (#6155).
- Fix: restored the `and_`. `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. No existing tests changed.

**3. Entity extraction returning only the first match**
- `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice in `find_entities`. I reverted that line. `tests/entity` passes (11 passed).

**4. Masked values becoming entities**
- Masking runs in the signal flow before entity extraction. A JSONPath aimed at a masked key read `"[REDACTED]"`, which became a shared entity. Instances with that entity were then deduplicated into one case.
- Fix: `find_entities` now masks the payload itself with `redact_raw` and skips any `"[REDACTED]"` value. This covers every caller, including the entity-type paths that run on unmasked payloads. The masking itself is unchanged.
- New test: `tests/entity/test_entity_redaction.py`. It fails without the fix. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**5. Signal payload masking (trace only, no code changes)**
- Masking happens in `redact_raw`, called from `signal_instance_create_flow`, which runs in the `signals process` loop, not in the POST handler.
- The POST handler commits the unmasked payload. The masked version replaces it only when the flow commits.

**Caveats**
- I did not run the full test suite, only the targeted suites above.
- The changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4