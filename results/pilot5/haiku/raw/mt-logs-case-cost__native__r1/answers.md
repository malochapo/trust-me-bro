**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. That makes the cost cut-off the latest of `stable_at`, `escalated_at` and `closed_at`, not the earliest. The function's own comment says "Determine the earliest relevant timestamp for cost calculation cut-off", and the code's purpose is to stop accruing participant time once the case becomes stable or closed. With `max`, a case keeps accruing until its latest milestone, so each participant's time jumps when the case is marked stable.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`. It was rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 between 18:14 and 18:15 UTC (events.log, after `dispatch-db-upgrade-65f7df6e`). `20f33137` is an ancestor of `65f7df6e`, so the fix is in that image. Later deploys (`main-51546e13`, 2025-09-04 16:52) still carry it, and HEAD still has the `max`.

**Evidence from the logs:**
- Before the deploy, the hourly diffs in cost-sync.log look normal, and there are no WARNING flags.
- The first WARNING flag is 2025-09-03 11:20 (case 5284, 3331 → 8804). The later flags are 5327 on 9/5, 5264 on 9/8 (3285 → 11987), 5363 on 9/9 and 5406 on 9/12. All are Stable cases, which is what a cut-off that moved later would produce.
- Case 5363 rose steadily by about 145 per hour from 9/4 until 9/9 12:20, then jumped 2261 → 6241 in one sync. That is the stable transition.

**Why tests missed it:** `tests/case_cost/test_case_cost_service.py::test_case_cost_stops_at_stable_time` only sets `stable_at` and never sets `escalated_at` or `closed_at` together with it, so the `min`/`max` difference is never exercised.

**Open question for you:** the commit title says "latest status timestamp", so the change may have been deliberate. If the intent was actually to stop at the first milestone, which the comment and the cost model suggest, the fix is to restore `min`, add a test where `escalated_at` precedes `stable_at`, and decide what to do about the flagged cases that already got overstated costs. I have not verified the `escalated_at` values for the flagged cases, since the logs don't include them.

I made no code changes.

----- next turn -----

The fix is in, with a regression test. The case-cost tests pass (20/20), and the test fails on the old code.

**Changes**
- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`. The cost cut-off is again the earliest of `escalated_at`, `stable_at` and `closed_at`, as the function's comment says.
- `tests/case_cost/test_case_cost_service.py`: new test `test_get_participant_role_time_seconds_stops_at_first_milestone`. The participant is assigned 3 hours ago, the case is escalated 2 hours ago and marked stable 1 hour ago. The test expects 3600 seconds (assignment to escalation), not 7200 (assignment to stable). It fails with `max` and passes with `min`.

**Full suite:** 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those same 8 on the original code, and they fail there too. They are not caused by this change, and I did not investigate them.

**Not done:**
- I did not commit.
- I did not correct the cost rows already written to the finance warehouse. The next hourly sync will recompute them from the fixed code, but the flagged cases (e.g. 5363) were overstated for the period since 2025-09-02 18:15. Whether to re-run the sync or adjust those rows is your call.

----- next turn -----

The TypeError is fixed, and cases with a missing employee cost or business-year hours now get a cost. The full suite has the same 8 failures as before my changes; all other tests pass.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours`. Some projects have `annual_employee_cost` set to `NULL`, so the division raised `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's `calculate_cases_response_cost` job caught it per case, logged it, and skipped the case. The log has 708 of these, first at 2025-09-08 15:55. Those cases got no cost at all.

**Fix:**
- `get_hourly_rate` now uses 50000 and 2080 when either value is `None`. These are the defaults declared on the Project model, and they are defined as constants `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS` in the same file.
- A project with a value of 0 still goes through the division as before, so I did not treat 0 as missing.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_defaults_when_missing` covers each missing field alone and both together.
- `test_calculate_case_response_cost_with_missing_project_values` runs the same calculation the scheduler runs and checks that a cost is returned.
- Both fail without the fix and pass with it.

**Not done:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I left it alone because you asked about the case cost job. It will fail the same way for incidents on projects with missing values, so it's worth a follow-up.
- I did not commit.

----- next turn -----

Here's the recap for the incident report. The six lines are at the end.

**Incident recap: inflated case response costs and missing-setting TypeError**

**1. Inflated costs.** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min` to `max` when picking the cost cut-off in `get_participant_role_time_seconds`. The cut-off became the latest of `escalated_at`, `stable_at` and `closed_at` instead of the earliest. Participant time therefore kept accruing after a case was marked stable. Cases were overstated from the moment they were marked stable, for example case 5363 went from 2261 to 6241 on 2025-09-09. The commit shipped in `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC. The first large jump in the cost-sync log is on 2025-09-03 (case 5284), and the later flagged cases are 5327, 5264, 5363 and 5406.
- Fix: restored `min`. Regression test `test_get_participant_role_time_seconds_stops_at_first_milestone` fails on the old code and passes now.
- Not done: the finance warehouse rows already written with inflated values are not corrected. The next hourly sync recomputes them from the fixed code, but the flagged cases were overstated from 2025-09-02 18:15 until then.

**2. Hourly TypeError.** Since 2025-09-08 15:55, the scheduler's `calculate_cases_response_cost` job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` 708 times. The job calls `get_hourly_rate`, which divides `annual_employee_cost` by `business_year_hours`. Some projects have no `annual_employee_cost`, so those cases were skipped and got no cost.
- Fix: a missing `annual_employee_cost` or `business_year_hours` now falls back to the Project model defaults, 50000 and 2080. Two regression tests cover this; both fail without the fix.
- Not done: `src/dispatch/incident_cost/service.py:133` has the same unguarded division for incidents. I did not change it, because it's outside the case cost job.

**3. Process.** The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They also fail on the original code, so they predate these changes. I did not commit any of the changes.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost