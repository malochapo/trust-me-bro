**Investigation 1: unprotected mutating routes and the deleted check**

I listed the POST, PUT, PATCH, and DELETE routes in the case and incident views that had no `PermissionsDependency`. Five handlers qualified. Two case handlers, `create_case_channel` and `create_case_resources`, are open on purpose, as is `create_incident`. The fifth, `delete_custom_event`, was a regression. Commit `328359b5` changed its permission from `IncidentCommanderOrScribePermission` to `IncidentEventPermission`, and commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the check entirely. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. The test passes with the fix and fails without it.

**Investigation 2: restricted cases visible to non-participants**

The cause was in `restricted_case_filter` (`src/dispatch/database/service.py`). Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the OR and dropped the `and_` that tied restricted visibility to participation. Every restricted case matched for non-admin users. The commit also undid the earlier security fix `b05613b5`. I restored the grouping. The tests in `tests/database/test_service.py` and `tests/case` pass (40 tests), and the existing test fails without the fix. I did not change any existing tests. I confirmed the filter is registered for `Case` and used by `search_filter_sort_paginate`, but I did not trace the cases list route end to end.

**Investigation 3: signal masking and the entity extraction bugs**

I traced `POST /api/v1/{organization}/signals/instances` (`src/dispatch/signal/views.py`). The route stores the raw payload unmasked and commits it. The payload is masked later, when the processing loop runs `signal_instance_create_flow`. This masking lives in `redact_raw` (`src/dispatch/signal/redaction.py`), and the default keys are set in `src/dispatch/config.py`. The masked value only overwrites the stored copy when that later step commits, so the unmasked payload is in the database for a while.

Two extraction bugs were found:
- **Only the first match:** commit `beb60cc4` added `[:1]` to the JSONPath match, so an entity type matching several fields produced only one entity. I reverted that line. `tests/entity` passes (11 tests).
- **Masked value became an entity:** an entity JSONPath pointing at a masked key matched the `[REDACTED]` placeholder, and that value became an entity. The deduplication filter then grouped unrelated instances. `find_entities` now extracts from a redacted copy and skips any match equal to the mask. I added `tests/entity/test_entity_redaction.py` with three tests. Two fail without the fix. The 46 tests in `tests/entity` and `tests/signal` pass with it.

**Open items**
- The `ObjectInUse` teardown error when a test imports `dispatch.main` is unexplained. I worked around it by importing the router directly.
- I did not check whether the create handlers enforce permissions inside the function body.
- All changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4