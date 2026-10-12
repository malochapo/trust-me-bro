## Recap

**1. Permission review of the case and incident APIs**
- Five data-changing handlers had no `PermissionsDependency` at the start. `create_case` and `create_incident` are open on purpose, because anyone may report. `create_case_channel` and `create_case_resources` never had a check (commits `ced74f33` and `f08a22b3`). They may be gaps, but they aren't regressions.
- The one regression was `incident.delete_custom_event`. Commit `28c21e1e` removed its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_event_views.py`. The test fails if the check goes missing.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc`, "flatten the restricted case filter", flattened `restricted_case_filter` into `open OR restricted OR email == user`. Every restricted case then matched for every non-admin user.
- I restored `and_(restricted, email == user)` in `src/dispatch/database/service.py`. I didn't add a regression test for this one.

**3. Signal instance flow and masking**
- `POST /signals/instances` only stores the instance. The scheduler later runs `signal_instance_create_flow`, which masks `raw` with `redact_raw`, extracts entities, filters, and then opens a case or stops.
- Masking matches whole key names only, case-insensitively and at any depth.
- The API view commits the raw payload before the scheduler masks it, so the unmasked payload is written to the database. The same unmasked payload is returned in the POST response.
- Masking was introduced by `d2675cf4`.

**4. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the match list. I removed it and `tests/entity` passed.

**5. Unrelated instances grouped into one case**
- After masking, a JSONPath on a masked key matches the literal `[REDACTED]` in every instance. That became one shared entity, and the deduplication filter grouped the instances.
- `find_entities` now skips any value equal to `MASK`, and I added a test in `tests/entity/test_entity_service.py`.
- This was a consequence of the masking commit `d2675cf4`, not a separate commit.

**State.** Nothing is committed. I only ran the tests under `tests/database`, `tests/case`, `tests/incident`, `tests/entity` and `tests/signal`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95