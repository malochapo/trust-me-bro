**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`. The cut-off used to be `min(timestamps)` and is now `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at` for any case that is not New or Triage. With `min`, a participant's time stops at the first lifecycle event. With `max`, it runs until the last one, so every participant's billed hours can grow well past the point where the case stopped being active.

**Deploy:** the commit is in `65f7df6e`, and that image (`registry.example.com/dispatch:main-65f7df6e`) rolled out to dispatch-web and dispatch-scheduler on **2025-09-02 at 18:14 UTC** (`events.log` line 2080). The next image, `main-51546e13`, rolled out on 2025-09-04 at 16:52. Both contain the change. The only commit touching `src/dispatch/case_cost/` in the window is `20f33137`.

**What the logs show:**
- Case 5363's classic cost grew about 145 per hour as expected until Sept 5 at 16:20 (2261). It then stayed flat, with no diffs logged, until Sept 9 at 12:20, when it jumped to 6241 at the moment the case was marked Stable.
- The same pattern appears in four other Stable cases flagged after the deploy: 5284 (Sept 3, 3331 → 8804), 5327 (Sept 5), 5264 (Sept 8, 3285 → 11987) and 5406 (Sept 12, 1975 → 4945).
- Across the whole window, cost jumps of more than 30% and more than 200 happen only seven times. Each is a case that later went Stable.
- The one jump before the deploy is case 5274 on Aug 27 (270 → 490), which is small and not flagged.

**Confidence and gaps:** I haven't confirmed the mechanism against the database. The logs contain only the cost totals, not the per-case `stable_at`, `escalated_at` or `closed_at` values or the participant assignment times. The explanation fits the timing and the pattern, but the exact size of each jump would need those timestamps. Two things would settle it: the timestamps for case 5363, and a re-run of `calculate_case_response_cost_classic` on that case with `min` in place of `max`. I also haven't checked whether `src/dispatch/incident_cost/service.py` has the same `min`/`max` logic, since the finance numbers for incidents may be affected too.

I haven't changed any code. Changing `max` back to `min` in `case_cost/service.py:353` looks like the fix, but it should be checked against cases that were correctly billed before the deploy before it ships.

----- next turn -----

The fix is in place and the regression test catches the bug. The changes are uncommitted in the working tree.

**Fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. The cut-off is again the first lifecycle event (stable, escalated or closed), so participant time stops when the case stops being active rather than running until it is closed.

**Regression test:** `test_get_participant_role_time_seconds_stops_at_first_lifecycle_event` in `tests/case_cost/test_case_cost_service.py`. It builds a case that went stable an hour before it was closed, with an assignee who is still assigned. The expected time is one hour. On the unfixed code it fails with 7200 seconds, which is the inflation seen in the finance data. It passes with the fix.

The existing `test_case_cost_stops_at_stable_time` did not catch this because it only sets `stable_at`, where `min` and `max` give the same result.

**Test results:**
- `tests/case_cost` and `tests/incident_cost`: 35 passed.
- Full suite: 360 passed, 4 skipped, 8 failed. Those 8 are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those files on the original code, and the same 8 fail there, so they predate this work and I haven't investigated them.

**Things to check:**
- The commit message for `20f33137` says "use the latest status timestamp", so its author may have intended `max` for some reason I don't know. Their intent isn't recorded in the repo. The existing test documents the stop-at-stable behaviour, and the finance numbers were correct before the deploy, so I went with `min`. If the author had a specific case in mind, that case needs a separate fix.
- The fix only affects future cost calculations. Cases already inflated in the warehouse (5363, 5284, 5264, 5327, 5406 and others) will need their costs recalculated. The hourly sync should correct them on its next run, but I haven't verified that.
- I did not commit or deploy anything.

----- next turn -----

The TypeError is fixed. Cases on projects with a missing annual employee cost or business year hours now get a cost, using the project model's defaults. The new test passes, and the full suite has the same 8 failures as before I started, which also occur on the original code.

**Cause:** the hourly job calls `get_hourly_rate(project)` in `src/dispatch/case_cost/service.py`, which runs `math.ceil(project.annual_employee_cost / project.business_year_hours)` with no check for `None`. For a project where either value is `NULL`, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's per-case handler catches it, logs it, and skips that case. The log has 708 of these errors, and the first is on 2025-09-08 at 15:55. The Column defaults only apply on insert, so projects whose values were nulled after creation keep `NULL`. I can't tell from the logs what nulled them. No deploy happened on Sept 8, so this points to a data change, not a code change.

**Changes:**
- `src/dispatch/project/models.py`: `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080` are now module constants. The column defaults and the `ProjectBase` defaults use them, so the values live in one place.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes the defaults when either value is `None`. It checks `is None` rather than using `or`, so an annual cost of 0 is still honoured.
- `tests/case_cost/test_case_cost_service.py`: `test_get_hourly_rate__missing_project_values_use_defaults` sets both values to `None`, checks the rate is `ceil(50000 / 2080) = 25`, and checks that `calculate_case_response_cost` returns both models' costs. It failed before the fix.

**Two things to check:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I left it alone because you asked about the case cost job. If incident costs hit the same nulls, they fail the same way.
- Projects with `NULL` values still have those values in the database. The fix only changes the calculation. If you want the stored values filled in, that needs a data update, which I haven't done.

I haven't committed anything.

----- next turn -----

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