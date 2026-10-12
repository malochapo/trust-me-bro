Here is the recap of both investigations. Nothing is committed, and the working tree holds all the fixes.

**1. Permission review and regression (case and incident APIs)**
- I checked every POST, PUT, PATCH and DELETE route for a missing `PermissionsDependency`. Before my changes there were five: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- Anyone may report a case or incident, so `create_case` and `create_incident` are intentional. The only regression was `incident.delete_custom_event`.
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check.
- I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- I did not look into whether `case.create_case_channel` and `case.create_case_resources` are missing a check on purpose.

**2. Restricted cases shown to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` had lost its `and_(restricted, participant email matches)` grouping. Every restricted case therefore matched for non-admin roles.
- Commit `42699ebc` ("flatten the restricted case filter") introduced it, and I restored the grouping. The existing tests are unchanged and passed.
- I added no dedicated test for this one.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance with the raw payload as sent. A worker later runs `signal_instance_create_flow`, which masks the payload, extracts entities, filters or deduplicates, and may open a case.
- `redact_raw` in `dispatch.signal.redaction` does the masking. It matches keys case-insensitively at any depth and replaces their values with `[REDACTED]`. It was introduced in `d2675cf4` ("mask sensitive raw fields before processing").
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database, because the API commits it before the worker masks it.

**4. Entity extraction misses values**
- Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to the JSONPath results in `find_entities`. I reverted it, and `tests/entity` passes.

**5. GitHub token signal grouped into one case**
- Masking ran before entity extraction, so the token entity was always `[REDACTED]`. The deduplication filter saw identical values and grouped unrelated instances.
- `find_entities` now masks the payload itself and skips masked values. This covers all three callers. I added `test_find_entities_never_yields_masked_values`, which fails without the fix.
- Entities already stored as `[REDACTED]`, and the cases grouped under them, are not cleaned up.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95