Recap of today's three investigations. Nothing is committed yet. The changes are uncommitted in the working tree.

**1. Unguarded write routes (case and incident APIs)**
Five write routes had no `PermissionsDependency` at HEAD. Three are case routes: `create_case`, `create_case_channel`, and `create_case_resources`. Two are incident routes: `create_incident` and `delete_custom_event`. Creating a case or incident is meant to be open to anyone, so those are design choices. `delete_custom_event` was a regression. Its `IncidentEventPermission` check was removed in `28c21e1e` (Sam Ortega, 2025-07-14, "refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py`. I also added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I confirmed the test fails with the line removed.
Still open: `create_case_channel` and `create_case_resources` have never had a permission check (added in `ced74f33` and `f08a22b3`). I did not change them. Adding `CaseEditPermission` is a one-line change each if you want it.

**2. Restricted cases visible to non-participants**
`restricted_case_filter` in `src/dispatch/database/service.py` had lost its participant check. Its `or_` included `Case.visibility == Visibility.restricted` as a bare term, so every restricted case passed. The check was flattened in `42699ebc` (Sam Ortega, 2025-09-02, "refactor(database): flatten the restricted case filter"). I restored the `and_` so restricted cases show only to their participants. Admin, owner, and manager roles are unchanged. `tests/database/test_service.py` and `tests/case` pass (40 passed). The existing restricted-case test fails without the fix. I did not change any tests.

**3. Entity extraction and masked values**
- **Extraction bug:** `beb60cc4` (Sam Ortega, 2025-09-02, "perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches. That kept only one entity per entity type. I removed the slice. `tests/entity` failed with `1 == 2` before and passes now.
- **Grouping bug:** the signal flow masks the payload before entity extraction. A JSONPath aimed at a masked key therefore matched the `"[REDACTED]"` placeholder, and every such instance got the same entity. The dedup filter then grouped them. I added a guard in `find_entities` (`src/dispatch/entity/service.py`) that skips any match equal to `MASK`. That covers all callers, since they all go through `find_entities`. I added `tests/entity/test_entity_masking.py`, which includes an unmasked control case. The new test fails without the guard. `tests/entity` passes (13 passed).
- **Masking:** `redact_raw` in `src/dispatch/signal/redaction.py` masks values for keys that match case-insensitively at any depth. The masking is unchanged.
- **Open issue:** unprocessed instances keep the unmasked payload in the database until the flow runs. Re-extracting entities from one of them can still turn the real token into an entity value. The guard only covers the placeholder.

I did not run the full test suite.

```
UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4
```