Five data-changing routes declare no `PermissionsDependency` in their route definition. Neither `APIRouter()` sets router-level dependencies. I read the decorators in both files and did not run the app.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

Number 5 stands out. Every other incident event route (create, update, export) requires `IncidentEventPermission`, and the equivalent case route `delete_custom_event` requires `CaseEventPermission`.

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency`. The two GET routes with permissions (`generate_tactical_report` and `generate_summary`) don't change data through the API, so they are out of scope.

I only checked for the declaration. Other auth may still apply, such as the authenticated-organization router in `api.py` or checks inside the function bodies. I didn't check either. I haven't changed any code.

----- next turn -----

Yes, one of them was a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I've restored its check and added a test. I haven't committed anything.

**The regression.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The commit message describes a tidy-up, but the diff is a single-line removal of the permission check. Without it, any authenticated user could delete incident timeline events. The sibling create, update and export routes, and the case equivalent, all still require an event permission.

**Not regressions.** The two case routes, `create_case_channel` (added in `ced74f33`) and `create_case_resources` (added in `f08a22b3`), never had a permission check. They have been open since they were introduced. If you want them guarded too, that's a separate hardening change. I haven't touched them.

**Changes**
- `src/dispatch/incident/views.py`: the original `IncidentEventPermission` dependency is back on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` (new): looks up the route on the incident router and asserts it carries a `PermissionsDependency` containing `IncidentEventPermission`.

**Verification.** The test passes with the fix. With the fix stashed, it fails. I ran it with `python -m pytest`, and it doesn't need the database.

----- next turn -----

Fixed. The security team member was seeing restricted cases they don't take part in because of commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause.** The commit was described as a flattening refactor, but it changed what the filter does in `restricted_case_filter` in `src/dispatch/database/service.py`. The visibility rule was:

```
open OR (restricted AND participant is the current user)
```

and became:

```
open OR restricted OR participant is the current user
```

Every restricted case now matched for non-admin roles, whether or not the user was a participant. The same condition also let the user's participation in any case through, regardless of that case's visibility. `restricted_incident_filter` still has the correct nested form.

**Fix.** I put the `and_(...)` back around the restricted-and-participant condition. This is the only change, and it matches the incident filter. I didn't edit any tests. `tests/database/test_service.py` passes in full (25 passed), including the restricted-case filter test. I haven't committed anything.

----- next turn -----



----- next turn -----

I've traced the whole path. Here is the short version, then the detail.

**Short answer:** the masking happens in `redact_raw()` in `src/dispatch/signal/redaction.py`, and the unmasked payload is written to the database first. The POST route commits the raw payload as sent. The masking only runs later, in the background flow.

**1. Ingestion: `POST /instances`, `create_signal_instance` in `src/dispatch/signal/views.py:70`**
- It resolves the project and the signal definition, in this order:
  - the definition named in the request, if any;
  - otherwise one matched by `raw["externalId"]` or `raw["variant"]`;
  - otherwise the project's default definition;
  - otherwise a 404.
- It calls `signal_service.create_instance()` (`service.py:650`). That copies `raw`, drops `oncall_service`, round-trips it through `json.dumps`/`json.loads`, and builds the `SignalInstance`. It also validates that the `id` is a UUID, returning 400 if not.
- The view then runs `db_session.commit()`. A duplicate id returns 409.
- It does not call the create flow. `background_tasks` is accepted as an argument but never used.

**2. Processing: `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46`**
- Instances are picked up later by the scheduled batch processors: `process_signal_batch` and `process_organization_signals` in `flows.py`, and the loop in `cli.py` (~line 1004). They select instances where `filter_action` and `case_id` are both null.
- **Masking:** the first thing the flow does is `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`). This is before entity extraction.
- Next it extracts entities from the (now masked) payload using the signal's entity types plus the global ones.
- `signal_service.filter_signal()` (`service.py:866`) then applies snooze filters, then dedup filters. If neither filter acts, it sets `filter_action = none`.
- **Filtered out:** if a filter acted (snooze or deduplicate), the flow returns. It attaches the existing case and refreshes the Slack signal message if there is one.
- **Stored only, no case:** canary instances, and signals with `create_case` off, are stored and the flow returns.
- **Case opened:** otherwise it works out case type, priority, oncall assignee and conversation target. It builds a `CaseCreate` with `Visibility.open`, calls `case_service.create`, and links the instance to the case. The case gets the signal's name and description, not the raw payload.

**3. Which function masks, and which keys**
- The function is `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`.
- It returns a copy in which the value of any matching key is replaced by `"[REDACTED]"`. Matching ignores case and applies at any depth, inside dicts and lists. Non-container values are left alone.
- The default keys are `password,secret,api_key,session_token,authorization`. This comes from the `SIGNAL_REDACTED_RAW_FIELDS` setting (`config.py:98`), which can be overridden by environment variable.
- Matching is on exact key names, not substrings. A key like `db_password`, `apiKey` or `access_token` is not masked.

**4. Is the unmasked payload written to the database?**
- **Yes.** The POST view commits the raw payload as received (`views.py`, after `create_instance`). The row sits in the database unmasked until the background flow picks it up and commits the masked version.
- That window can be long if the scheduler is slow or backed up. Instances whose processing throws an error are rolled back before the masked value is committed, so they stay unmasked and get retried.
- Entity extraction does run on the masked copy, so extracted entities won't contain the masked values. Values under keys the list doesn't cover are never masked.
- Any code that reads `raw` before the flow runs, such as `GET /instances`, would see the original values.

**Side notes I noticed but didn't dig into**
- In `create_signal_instance`, `signal_definition` (and `external_id` and `variant`) are only assigned when `signal_instance_in.signal` is empty. A request that names the signal explicitly looks like it would hit an `UnboundLocalError`.
- `flows.py:52` has a `"%%s"` format string in a log call, which is a typo.

I haven't changed any code. The obvious fix would be to call `redact_raw` inside `create_instance` before the first commit. Say if you want that done.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match, so an entity type whose JSONPath matched several fields produced one entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment added with it. The fix is only in `src/dispatch/entity/service.py`, and I didn't touch any tests. `python -m pytest tests/entity` now passes (11 passed). Nothing is committed.

----- next turn -----

Masked values no longer become entities. Unrelated "GitHub: Personal access token exposed" instances should therefore stop landing in one case. I verified this with a new test, not against a live signal. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped), and nothing is committed.

**Cause.** The create flow masks the payload before extracting entities (`flows.py:60`). A JSONPath that points at the session token then matches the string `"[REDACTED]"`. `find_entities` turned that into an entity, and every instance got the same entity value. The signal's deduplication filter on that entity type then treated all those instances as duplicates and grouped them into one case.

**Fix.** The change is in `find_entities`, in `src/dispatch/entity/service.py`. Both extraction paths go through it: the signal create flow, and the entity-type create and update flows, which re-extract from stored payloads.
- It runs `redact_raw()` on a copy of the payload before applying the JSONPath. This matters because the POST route stores the payload unmasked until the background flow runs, so re-extraction from a stored payload could otherwise put a real secret into an entity.
- It also skips any match equal to `MASK`, so an already-masked payload can't produce an entity either.
- The masking itself is unchanged.

**Test.** `test_find_entities_never_creates_masked_entity` in `tests/entity/test_entity_service.py`. It covers both an unredacted stored payload and an already-redacted one. It checks that only the unrelated `user` field becomes an entity, for a direct `session_token` path and a `$..password` path. I confirmed it fails without the fix.

A payload that genuinely contains the literal value `[REDACTED]` also won't become an entity.

----- next turn -----

## Recap

**1. Permission review (case and incident APIs)**
- Five handlers changed data without a `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report one.
- `create_case_channel` and `create_case_resources` never had a check. I left them alone, but they could be hardened separately.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc` ("flatten the restricted case filter") broke the logic in `restricted_case_filter`. The rule became `open OR restricted OR participant`, so every restricted case matched. I restored the `and_` around the restricted-and-participant condition.
- The existing tests in `tests/database/test_service.py` are unchanged and pass.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits. The background create flow (`signal_instance_create_flow`) later masks the payload, extracts entities, applies the snooze and dedup filters, and then either opens a case or stores the instance without one.
- `redact_raw` masks the payload. It matches key names exactly, ignoring case, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database: the POST route commits it before the flow redacts it. I did not change this, and the fix would be to redact inside `create_instance`.

**4. Entity extraction**
- Commit `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. I reverted it, and `tests/entity` passes.
- Masked values were also becoming entities, because every instance got the same `[REDACTED]` value. That made the dedup filter group unrelated instances into one case. `find_entities` now masks a copy of the payload first and skips any masked value, and `test_find_entities_never_creates_masked_entity` covers it.

Nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, `tests/entity/test_entity_service.py` and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4