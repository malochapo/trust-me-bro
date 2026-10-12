**Recap**

**Security review (permissions).** I listed every POST, PUT, PATCH and DELETE handler in the case and incident routers that had no `PermissionsDependency`. Five did. Three of them are open on purpose or were never protected: `create_case`, `create_case_channel` and `create_case_resources` in the case API, and `create_incident` in the incident API. I left those alone. The fifth, `delete_custom_event`, was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. That test passes with the fix and fails against HEAD.

**Restricted cases visible to non-participants.** `restricted_case_filter` in `src/dispatch/database/service.py` had its participant check removed, so any non-admin user saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") caused it. I restored the `and_` that requires the participant match, the same as the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails against the old code and passes now.

**Entity extraction keeps only the first match.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup. I removed it. `tests/entity` went from one failure to passing.

**Masked values becoming entities.** The masking itself was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing"). It runs in the signal flow, but `find_entities` is also called on stored instances from `entity_type/service.py` and `entity_type/flows.py`, so masked fields could still become entities. A JSONPath pointing at a masked key yields `"[REDACTED]"`, and that shared value grouped unrelated instances. I moved the masking into `find_entities`, which now also skips matches equal to the mask. The masking function and key list are unchanged. I added `tests/entity/test_entity_redaction.py`, which fails without the fix and passes with it.

**Open items**
- Nothing is committed. The working tree has the changes above, plus the `[:1]` removal.
- I ran `tests/entity`, `tests/signal`, `tests/entity_type`, `tests/case`, `tests/incident` and `tests/database/test_service.py`. I did not run the full suite.
- `create_case_channel` and `create_case_resources` still have no permission check. They were never protected, so they are a separate decision.
- The unmasked payload is stored between the POST and the processing loop, and it stays there if processing fails before its first commit.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4