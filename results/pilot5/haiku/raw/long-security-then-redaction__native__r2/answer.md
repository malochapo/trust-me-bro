Here is the recap for the weekly report. Nothing is committed yet.

**1. Mutating routes without a permission check (case and incident APIs)**
Five data-changing routes had no `PermissionsDependency` before my changes. Two are open by design: anyone may report a case or an incident. The other three are `create_case_channel` and `create_case_resources` in `case/views.py`, and `delete_custom_event` in `incident/views.py`. I did not find a history of a removed check for the first two, so I treated them as unguarded, not as regressions.

**2. Custom event delete regression**
`delete_custom_event` had lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check and added `tests/incident/test_incident_views_permissions.py`. That test fails without the fix. I did not confirm the route-level dependencies at mount time in `src/dispatch/api.py`, so the coverage of the mounted routes is still unverified.

**3. Members seeing restricted cases they are not part of**
`restricted_case_filter` in `src/dispatch/database/service.py` included `Case.visibility == Visibility.restricted` with no participant check. Any member could see every restricted case. Introduced by `b05613b5` (#6155, "sec(authz): addresses authorization bypass and information disclosure issues"). The fix requires the participant match, the same shape as the incident filter. `test_restricted_case_filter_with_test_data` passes again.

**4. Entity extraction returned only the first match**
`beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`. I removed it. `tests/entity/test_entity_service.py::test_find_entities_with_field_only` was failing because of this. It was earlier listed as pre-existing; it was not.

**5. Entities from masked values (dedup grouping)**
Masking runs in `signal_instance_create_flow` before entity extraction, so a JSONPath on `session_token` matched the placeholder `"[REDACTED]"`. That created a shared entity, and the dedup filter grouped unrelated instances. Two paths were involved. `recalculate_entity_flow` and `entity_type/service.py` call `find_entities` on instances stored before masking ran. `find_entities` now masks the payload itself and skips any match equal to the placeholder. The new test is `tests/entity/test_entity_masking.py`. It fails without the fix. Masking itself is unchanged.

**Results:** the full suite gives 363 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`. They need network access to download the tiktoken encoding, which this sandbox does not have.

**Open items for the report**
- `recalculate_entity_flow` assigns the result of `.append()`, which is `None`. Entity recalculation never runs. This is a separate bug I did not fix.
- `find_entities` has no regex-based extraction. Entity types with only a regular expression produce nothing. I did not check whether this is a regression.
- `update_signal_instance` writes the raw payload without masking, and the flow is not re-run after an update.
- The commit dates do not match "this week". `beb60cc4` is from 2025-09-02 and `b05613b5` is from 2025-07-29. Check these dates before you publish.

RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
VISIBILITY_BUG: b05613b57649306ddbf38a3a5083a16bdf947c3a
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95