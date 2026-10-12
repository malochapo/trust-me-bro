Here is the recap for the incident report. Nothing is committed yet.

**Cost inflation (case response costs)**
- **Cause:** commit `20f33137` changed `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. For a case that was stable, escalated or closed, participant time then ran until the latest lifecycle event instead of the first, so classic costs grew well past the point where the case stopped being active.
- **Deploy:** `main-65f7df6e` rolled out to dispatch-web and dispatch-scheduler on 2025-09-02 at 18:14 UTC. It contains `20f33137`.
- **Impact:** the first clearly inflated case is 5284, which jumped from 3331 to 8804 on 2025-09-03. Other cases show the same pattern: 5327, 5264, 5363 and 5406, each jumping when marked stable. The logs record only hourly totals, not the per-case timestamps, so I can't prove that no smaller inflation started earlier that day.
- **Fix:** `src/dispatch/case_cost/service.py` now uses `min` again. The regression test `test_get_participant_role_time_seconds_stops_at_first_lifecycle_event` fails on the old code (7200 seconds instead of 3600) and passes with the fix.
- **Open point:** the commit message says "use the latest status timestamp", so the author may have intended `max` for a reason that isn't recorded. The existing stable-cut-off test and the pre-deploy numbers support `min`. Cases already inflated still need their costs recalculated.

**Hourly TypeError (missing project values)**
- **Cause:** `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours` with no check for `None`. A project with a `NULL` annual employee cost raised a `TypeError`, and the scheduler logged it and skipped the case. The log has 708 of these, starting 2025-09-08 at 15:55. No deploy happened that day, so the nulls most likely came from data changes.
- **Fix:** `get_hourly_rate` now uses the project model's defaults (50000 and 2080, now named constants in `src/dispatch/project/models.py`) when a value is `None`. Regression test: `test_get_hourly_rate__missing_project_values_use_defaults`.
- **Open points:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division and isn't fixed. The `NULL` values remain in the database, so the defaults apply only at calculation time.

**Verification:** the full suite gives 361 passed, 4 skipped and 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail on the original code, so they predate this work.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost