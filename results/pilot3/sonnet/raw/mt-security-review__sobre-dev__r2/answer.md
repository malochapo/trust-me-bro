## Recap

**Unprotected routes at the start.** Five handlers changed data without a `PermissionsDependency`:
- `case.create_case`, `POST /cases`
- `case.create_case_channel`, `POST /cases/{case_id}/resources/conversation`
- `case.create_case_resources`, `POST /cases/{case_id}/resources`
- `incident.create_incident`, `POST /incidents`
- `incident.delete_custom_event`, `DELETE /incidents/{incident_id}/event/{event_uuid}`

My first answer left `create_incident` off the list. I had noticed it had no dependency but skipped it because I hadn't read its body. It belongs on the list. I re-read every route decorator in both files, and there are no others.

**What was a regression.** Only `incident.delete_custom_event` was. Commit `28c21e1e` removed its `IncidentEventPermission` check in a "tidy" refactor. I restored the check and added `tests/incident/test_incident_view_permissions.py`. That test fails without the fix and passes with it.

**Open on purpose.** `create_case` and `create_incident` are open so anyone can report a case or incident, as you said.

**Not regressions.** `create_case_channel` and `create_case_resources` never had a check, so they are an original gap rather than a regression. They are worth a separate review, and I didn't change them.

**Visibility bug.** Commit `42699ebc`, "flatten the restricted case filter", rewrote `restricted_case_filter`. It turned "restricted and the user is a participant" into three separate alternatives. As a result, every restricted case matched for non-admin users. I restored the `and_` grouping. The 41 tests in `tests/database`, `tests/case` and `tests/incident` pass, and I didn't change any existing tests. I didn't run the full suite or add a test for the filter. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc