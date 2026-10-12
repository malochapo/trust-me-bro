Five mutating routes have no `PermissionsDependency` in their route definition. Nothing was changed.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` (create_case), line 162
2. `POST /{case_id}/resources/conversation` (create_case_channel), line 236
3. `POST /{case_id}/resources` (create_case_resources), line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` (create_incident), line 117
5. `DELETE /{incident_id}/event/{event_uuid}` (delete_custom_event), line 503

I checked the router mounting in `src/dispatch/api.py`. Both routers are included under `authenticated_organization_api_router`, which only adds `get_organization_path` and no permission check, so it doesn't cover these five routes. I only checked route declarations, as asked. The handler bodies could still enforce permissions themselves, and I didn't look at that.

----- next turn -----

Yes, one of the five is a regression. The incident `DELETE /{incident_id}/event/{event_uuid}` route (delete_custom_event) lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit deleted only that one line. Before it, every version of the route carried the check, so it wasn't a design choice.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the route, matching its earlier form.
- `tests/incident/test_incident_event_permissions.py` (new): inspects the incident router and asserts the DELETE event route declares `IncidentEventPermission`. I checked that it passes with the fix and fails against the regressed file, using a temporary stash of `views.py`.

**Test results**
- `python -m pytest tests/case tests/incident tests/api`: 16 passed.

**Not regressions**
- `POST /{case_id}/resources` and `POST /{case_id}/resources/conversation` have never had a permission declaration in any version of `case/views.py` in the history I checked. I'm treating them as design choices, not regressions.
- `POST ""` for cases and incidents are the open reporting routes you mentioned.

I did not run the full test suite, only the directories above.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. Restricted cases were visible to every non-admin user, whether or not they were participants.

**Cause and introducing commit**
- The filter's `or_` had `Case.visibility == Visibility.restricted` as a standalone term, so any restricted case matched for any member.
- That was introduced by `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It removed the `and_(...)` grouping, so the restricted and participant checks stopped being conditioned on each other.
- The incident version of the filter has the grouping intact, which is why only cases were affected.

**Fix**
- Restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching `restricted_incident_filter`. Admin, owner and manager roles are still unfiltered.

**Tests**
- I did not change any tests.
- `python -m pytest tests/database tests/case tests/incident tests/api`: 41 passed.
- The existing tests don't seem to cover this leak, since they passed on the broken code too. I didn't verify that against the broken code directly, and I didn't add a regression test because you asked me not to change the tests.

I also left the earlier regression fix (incident delete-event permission) in place.

----- next turn -----



----- next turn -----

The raw payload is masked in memory, but the unmasked version is committed to the database first. Masking only happens later, when the background processor runs the flow.

**1. API entry point (`src/dispatch/signal/views.py`, `create_signal_instance`, ~line 72)**
- The route stores the payload as sent. It resolves the signal definition from `raw["externalId"]` and `raw["variant"]`, falling back to the default definition.
- It calls `signal_service.create_instance` and then `db_session.commit()`.
- `background_tasks` is declared but never used, and the route never calls the signal flow. The request returns the instance as-is.

**2. Storage (`src/dispatch/signal/service.py`, `create_instance`, ~line 680)**
- `raw=json.loads(json.dumps(signal_instance_in_raw))` writes the full, unmasked payload to `SignalInstance.raw` (a JSONB column, `signal/models.py:239`).
- At this point the raw payload is in the database unmasked.

**3. Processing (`src/dispatch/signal/flows.py`)**
- A scheduler loop (`process_organization_signals`, called at ~line 468) picks up instances with `filter_action` and `case_id` both null, through `get_unprocessed_signal_instance_ids`.
- `process_signal_batch` calls `signal_instance_create_flow` for each one and commits after each success, or rolls back on error.
- The CLI has a second caller at `cli.py:1004` that runs the same flow.

**4. Masking (`src/dispatch/signal/flows.py:59-60`, function `redact_raw` in `src/dispatch/signal/redaction.py`)**
- The first thing the flow does, before entity extraction, is `signal_instance.raw = redact_raw(signal_instance.raw)`.
- `redact_raw` returns a new structure. It walks dicts and lists recursively and replaces the value of any dict key whose name matches, case-insensitively, with `"[REDACTED]"`. Other values are returned unchanged.
- Key matching is exact after lowercasing, so `apiKey` does not match `api_key`. Only dict keys are checked, not values.
- Entity extraction runs after masking, so entities are derived from the masked payload.

**5. Default keys (`src/dispatch/config.py:98-102`)**
- `SIGNAL_REDACTED_RAW_FIELDS` comes from the environment and defaults to `password,secret,api_key,session_token,authorization`.
- Keys such as `token`, `client_secret`, `private_key` or `apiKey` are not masked unless they are added to the setting.

**6. Is the unmasked payload written to the database? Yes, in two cases.**
- **Always, at the API commit.** Step 2 commits the raw payload before any masking happens. Any reader of the table or the API sees the unmasked value until the flow runs.
- **If the flow fails.** The masked value is only persisted by a later commit: either the entity commit (only when entity types exist) or the commit in `filter_signal` (`service.py:896`), which runs on every successful flow. If the flow raises before that commit, `process_signal_batch` rolls back, and the instance keeps the unmasked payload. Since the instance then has no `case_id` and `filter_action` stays null, the scheduler retries it, but the raw value stays unmasked until a retry succeeds.

**Paths after masking**
- **Filtered** (snooze or dedup): `filter_signal` returns true, the flow returns early, and the masked raw is already stored.
- **Canary**, or the signal has `create_case` off: the flow returns after masking, and the masked raw is stored.
- **Opens a case**: the case is created from the signal name and description and the resolved priority, type and assignee. The raw payload is not copied into the case.

**Other observations**
- The AWS plugin (`plugins/dispatch_aws/plugin.py:113`) calls the same `create_instance`, so it has the same unmasked-first storage.
- No test in `tests/` references `redact` or `SIGNAL_REDACTED_RAW_FIELDS`, so the masking is untested.

I didn't change any code.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed the line in `find_entities` (`src/dispatch/entity/service.py`) from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`, so only the first match for each entity type was turned into an entity.

**Fix:** I removed the `[:1]` slice and the comment that justified it, restoring `matches = jpath.find(signal_instance.raw)`. No tests were changed.

**Tests:**
- `python -m pytest tests/entity`: 11 passed.
- `python -m pytest tests/entity tests/signal`: 43 passed, 1 skipped.

I haven't added a regression test for multiple matches. The entity tests were already failing before the fix, so they cover this case.

Uncommitted changes from earlier are still in the working tree: the restricted-case filter fix in `src/dispatch/database/service.py`, and the incident delete-event permission fix with its new test in `src/dispatch/incident/views.py` and `tests/incident/`.

----- next turn -----

The cause was that `find_entities` extracted entities from the masked payload, and the constant `[REDACTED]` value became the entity. Every instance with a masked token produced the same entity value, so the deduplication filter grouped unrelated instances into one case.

**Fix** (`src/dispatch/entity/service.py`)
- `find_entities` now masks the payload itself with `redact_raw`, the same function the flow already uses, before matching JSONPaths. This covers the entity-type reprocessing paths too (`entity_type/service.py:95` and `entity_type/flows.py:29`), which read the stored `raw`. That raw can still be unmasked if the flow failed before its commit.
- Matches whose value is the `MASK` marker are skipped, so a masked value can never become an entity.
- The masking itself (`redact_raw`, the default keys, and the flow's masking step) is unchanged.

**Test** (new file `tests/entity/test_entity_redaction.py`, no existing tests changed)
- `test_find_entities_never_returns_masked_value`: a `session_token` field with a JSONPath to it yields no entities.
- `test_find_entities_keeps_unmasked_values_next_to_masked_ones`: a non-sensitive `user` field still yields its entity.
- I checked the first test against the broken code (fix temporarily removed): it failed, and it passes with the fix restored.

**Results:** `python -m pytest tests/entity tests/signal`: 45 passed, 1 skipped.

Existing analyst cases that already grouped together are not corrected by this change. Instances created before the fix may still have entities that came from masked values; those would need the entities cleaned up separately.

----- next turn -----

## Recap

**Investigation 1: unguarded mutating routes and the regression**
- Case and incident routers have 13 mutating handlers each. Five declared no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, as you confirmed.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.
- Open question: `case.create_case_channel` and `case.create_case_resources` have never had a check in any commit I looked at. I did not change them. Someone needs to decide whether they are design choices or gaps.

**Investigation 2: restricted cases visible to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == Visibility.restricted` as a standalone OR term, so any member could see every restricted case.
- Commit `42699ebc` (flatten refactor, 2025-09-02) removed the `and_` grouping that `b05613b5` had added. I restored it. No existing tests were changed.
- Gap: no regression test covers this filter yet.

**Investigation 3: signal payload processing**
- Entry point: `POST /api/v1/{organization}/signals/instances` stores the raw payload with no masking. A scheduled job then runs `signal_instance_create_flow`, which masks the payload and extracts entities.
- Masking is done by `redact_raw` in `src/dispatch/signal/redaction.py`, added in `d2675cf4` (2025-07-03). By default it masks `password`, `secret`, `api_key`, `session_token`, and `authorization`, matched case-insensitively at any depth.
- The unmasked payload is written to the database at the API commit, before any masking runs. The masked version is only committed later, so if the flow fails, the unmasked payload stays in the database.
- **Extraction bug:** commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I removed the slice. `tests/entity` passes (11 tests).
- **Masked-entity bug:** `find_entities` extracted entities from the masked payload, so the constant `[REDACTED]` value became an entity. Analysts saw unrelated token exposures grouped into one case because of the deduplication filter. I fixed `find_entities` to mask the payload itself and skip masked values, and added `tests/entity/test_entity_redaction.py`. The new test fails without the fix and passes with it. `tests/entity` and `tests/signal` pass (45 passed, 1 skipped).
- Open: entities already created from masked values are not cleaned up by this fix.

Not done: I did not run the full test suite, and the changes are uncommitted.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4