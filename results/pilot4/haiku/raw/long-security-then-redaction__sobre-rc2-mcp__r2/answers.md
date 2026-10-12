Five mutating endpoints have no `PermissionsDependency` declared on their route:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

I checked the router objects and found no router-level `dependencies=`, so these routes have no permission check at all. I did not check whether `get_current_case` or `get_current_incident` enforce access, so those two case routes and the incident delete may still be guarded by the dependency that loads the record.

No code was changed.

----- next turn -----

The one regression I found is the incident custom-event delete route. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency as a one-line deletion, and the commit message says nothing about permissions. The other routes from the earlier list are not regressions:

- **`create_case_channel`** (`POST /{case_id}/resources/conversation`) and **`create_case_resources`** (`POST /{case_id}/resources`) were added without a permission check in `ced74f33` and `f08a22b3`. This looks like a design gap, not a regression, so I left them alone.
- **`create_case`** and **`create_incident`** are the open-to-anyone reporting routes you mentioned, so I left them alone too.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_views.py` (new): checks that the `DELETE /{incident_id}/event/{event_uuid}` route declares a `PermissionsDependency` that includes `IncidentEventPermission`. It is a structural check on the router, so it does not need a database user or fixtures.

**Verification**
- With the fix, `python -m pytest tests/incident/test_incident_views.py` passes.
- With the view change stashed, the same test fails, so it catches the removal.

I ran only the new test file, not the full suite.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. It is fixed, and the existing tests are unchanged.

**Cause:** the filter's `OR` had `Case.visibility == Visibility.restricted` as a standalone term. That made every restricted case visible to any non-admin user, whether or not they were a participant. The email match was also a standalone term, so it was not tied to restricted cases either. The incident filter does this correctly with an `and_`, so I restored the same `and_` in the case filter:

```python
or_(
    Case.visibility == Visibility.open,
    and_(
        Case.visibility == Visibility.restricted,
        IndividualContact.email == current_user.email,
    ),
)
```

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). Its diff removed the `and_(...)` wrapper, and the commit message describes it as a refactor only.

**Verification:**
- Without the fix, `tests/database/test_service.py -k restricted_case_filter` fails with `assert 4 == 3`, which is the member seeing an extra restricted case. With the fix, all 5 pass.
- `tests/database`, `tests/case`, and `tests/incident` together: 41 passed.

I did not add a new test, since the existing one already covers this.

----- next turn -----



----- next turn -----

The unmasked payload is written to the database. The POST handler commits the raw payload before any masking runs, and the masking only happens later in the processing flow. I traced this by reading the code; I did not run the endpoint.

**Path**

1. **`POST /api/v1/{organization}/signals/instances`**, `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project and signal definition, then calls `signal_service.create_instance` and `db_session.commit()` (line ~120). No masking happens here. The commit writes `raw` exactly as sent. The 409 path on `IntegrityError` is also here.
2. **`signal_service.create_instance`**, `src/dispatch/signal/service.py:650`. It JSON round-trips `raw` (line 680) and adds the row to the session. It does not mask anything.
3. **Processing loop.** Nothing is queued from the view; `BackgroundTasks` is a parameter but unused. Instead, `main_processing_loop` (`src/dispatch/signal/flows.py:441`) calls `process_organization_signals` (line 406), which takes unprocessed IDs from `get_unprocessed_signal_instance_ids` (`service.py:900`: `filter_action IS NULL` and `case_id IS NULL`, oldest first, 500 at a time). `process_signal_batch` (line 385) calls `signal_instance_create_flow` for each and commits after each one; on exception it rolls back.
4. **`signal_instance_create_flow`**, `src/dispatch/signal/flows.py:46`. The first step that touches the payload is line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`. Entity extraction (lines 63–75) runs after this, so it sees the masked copy.
5. **Filter.** `signal_service.filter_signal` (`service.py:866`, called at flows.py:78) handles snooze and deduplication. If it returns True, the flow returns early and the instance is kept with its `filter_action` and no case.
6. **Case.** If not filtered and `signal.create_case` is set (line 106), the flow resolves case type, priority, severity and oncall, then calls `case_service.create` and `case_flows.case_new_create_flow` (lines 153–208).

**Where masking happens**

- `redact_raw` in `src/dispatch/signal/redaction.py:10`. It returns a copy, and `_redact` recurses through dicts and lists. A key whose lowercased name is in the set is replaced with `"[REDACTED]"`. Other scalars are returned unchanged.
- Default keys, from `src/dispatch/config.py:98`, read from the `SIGNAL_REDACTED_RAW_FIELDS` env var: `password, secret, api_key, session_token, authorization`.
- Matching is exact on the lowercased key, not substring. So `apiKey`, `api-key`, `x-api-key` or `token` are not masked by default. Values under keys that aren't listed are not masked either.
- `redact_raw` is called only in `signal_instance_create_flow`. A grep finds no other caller.

**Is the unmasked payload persisted?**

Yes, in two places:

- **At API time.** The view commits at line 120 before the flow runs, so `signal_instance.raw` is stored unmasked. The flow only redacts in memory at line 60, and that is written only when `process_signal_batch` or the CLI loop (`src/dispatch/cli.py:1004`) commits after the flow. Until then the DB holds the unmasked value. If the flow raises after line 60, the rollback reverts it, and the next run redacts it again. The unmasked version stays in the table until the batch succeeds.
- **Other paths.** `signal_service.create_instance` is also called from `flows.create_signal_instance` (line 231, used by the AWS plugin at `src/dispatch/plugins/dispatch_aws/plugin.py:113`), which doesn't redact at all. Rows from that path are masked only if they later go through `signal_instance_create_flow`.

Two more places where the unmasked payload is exposed:

- The POST response. `create_signal_instance` returns `SignalInstanceRead`, which inherits `raw` from `SignalInstanceBase` (`models.py:394`), so the caller gets the unmasked payload back.
- `GET /instances` returns `raw` unmasked too (`search_filter_sort_paginate`), so it is exposed to anyone who can read signal instances.

I did not change any code. If you want, I can check whether `SignalInstanceRead` or the GET endpoint is meant to expose `raw`, or look at the test coverage for `redact_raw`.

----- next turn -----

The cause is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match. I reverted that line to `matches = jpath.find(signal_instance.raw)`, so every match of a JSONPath now becomes an entity again.

**Verification:**
- `tests/entity`: 11 passed with the fix.
- With the committed version of the file, `tests/entity/test_entity_service.py::test_find_entities_with_field_only` fails with `len([<Entity #9>]) == 1`, which is the reported symptom.
- `tests/entity` and `tests/signal` together: 43 passed, 1 skipped.

The existing tests are unchanged. The fix is uncommitted. The working tree also still contains the earlier changes from this session: the `database/service.py` case-visibility fix, the restored `delete_custom_event` permission in `incident/views.py`, and the new `tests/incident/` directory.

----- next turn -----

Masked values can no longer become entities. The new test passes with the fix and fails on the committed code.

**Cause:** `find_entities` in `src/dispatch/entity/service.py` ran JSONPath against `signal_instance.raw`, the unmasked payload. Masking only happens in `signal_instance_create_flow`, so any other caller got the raw value. The entity-type reprocessing paths (`entity_type/service.py:95` and `entity_type/flows.py:29`) do this, and they read stored payloads that haven't been processed yet, which are still unmasked.

**Fix**, in `src/dispatch/entity/service.py`:
- `find_entities` now searches `redact_raw(signal_instance.raw)`, so every caller gets the masked copy. `redact_raw` and its key list are unchanged.
- Matches whose value equals `MASK` are skipped. Without this, the placeholder `"[REDACTED]"` itself became an entity. Every masked instance would then share that entity and group together, which is the symptom you described. The new test caught this.

**Test:** `test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py`. It puts a session token under a listed key, both at a plain path and inside a list, and checks that only the non-sensitive `actor` becomes an entity. It also checks that the stored payload is still unmasked after extraction.

**Verification:**
- `tests/entity`, `tests/signal`, and `tests/entity_type`: 50 passed, 1 skipped.
- On the committed `entity/service.py`, the new test fails. `test_find_entities_with_field_only` also fails there because of the `[:1]` change from `beb60cc4`.

The fix is uncommitted, and the working tree still includes the earlier changes from this session.

----- next turn -----

## Recap

**Investigation 1: unprotected mutating routes and the incident regression**

I listed the POST, PUT, PATCH and DELETE routes in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` that have no `PermissionsDependency`. Three case routes and two incident routes qualified. `create_incident` is open by design. Of the rest, only `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views.py`, which fails if the check goes missing again. The two open case sub-routes were not verified for object-level access checks, and I did not change them.

**Investigation 2: cases list showing restricted cases to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == Visibility.restricted` as a standalone OR term, so any non-admin saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that tied restricted cases to participation. I restored it to match `restricted_incident_filter`. `test_restricted_case_filter_with_test_data` fails without the fix (`4 == 3`) and passes with it.

**Investigation 3: masking and the signal endpoint**

Tracing `POST /signals/instances`, the payload is committed unmasked in `create_signal_instance` before the processing flow runs. `signal_instance_create_flow` masks it in memory at `src/dispatch/signal/flows.py:60`. The masking function is `redact_raw` in `src/dispatch/signal/redaction.py`, with default keys `password, secret, api_key, session_token, authorization`. The POST response also returns the raw payload unmasked.

**Entity extraction**

- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice, so only the first match became an entity. I reverted it. `test_find_entities_with_field_only` fails on the committed code and passes now.
- Entity extraction ran on the unmasked payload, which affected the entity-type reprocessing paths. `find_entities` now searches a masked copy. Matches equal to the `[REDACTED]` placeholder are skipped, so the placeholder cannot group unrelated instances. `test_find_entities_never_extracts_masked_values` covers this and fails on the committed code.

**Test status:** `tests/entity`, `tests/signal`, and `tests/entity_type`: 50 passed, 1 skipped. Earlier runs covered `tests/database`, `tests/case` and `tests/incident`, with 41 passing.

**Open items**
- Nothing is committed. The working tree contains the fixes for the case filter, the incident route, and entity extraction, plus the new tests.
- The POST response and `GET /instances` both return the unmasked payload. I did not change this, since the request was to keep masking as it is.
- Whether the two open case sub-routes check object access was not verified.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4