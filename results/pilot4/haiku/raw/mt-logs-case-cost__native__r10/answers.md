**Root cause:** commit `20f33137` changed the cost cut-off from the earliest milestone to the latest, which makes a case's response cost jump whenever it moves from escalated to stable or closed. It shipped to production in image `main-65f7df6e`, deployed to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14–18:15 UTC**. I haven't changed any code.

**The change:** `src/dispatch/case_cost/service.py:353` in `get_participant_role_time_seconds` now reads `participant_role_renounced_at = max(timestamps)`. The previous line was `min(timestamps)`. The `timestamps` list holds `stable_at`, `escalated_at` and `closed_at`. The comment directly above still says "Determine the earliest relevant timestamp for cost calculation cut-off", and the commit message says "latest status timestamp", so the code contradicts both.

**How it produces the jump, using case 5363:**
- Through Sep 5 16:20 the case's cost grew about 145 per hour, as expected for an active case.
- At 16:20 on Sep 5 it froze at 2261. That is consistent with the case escalating: with only `escalated_at` set, the cut-off is that timestamp under either `min` or `max`, so the freeze is the existing design, not the regression.
- It stayed at 2261 for about three days, with no changes logged by cost-sync.
- When the case was marked stable, the cut-off became `max(stable_at, escalated_at) = stable_at`. Under `min` it would have stayed at `escalated_at`. The cost moved to 6241 in the Sep 9 12:20 run.
- The jump of 3980 is about 27 hours at 145 per hour. That fits the escalated-to-stable interval once the code's 8-hour-per-day cap is applied, but I could not check the exact timestamps because the data has no case timestamps.

**Caveats:**
- The 3425 → 1243 drop for 5363 on Sep 5 09:20 doesn't fit this mechanism. I didn't explain it.
- The existing test `test_case_cost_stops_at_stable_time` (`tests/case_cost/test_case_cost_service.py:355`) only sets `stable_at` with no escalation, so it can't detect the regression. I didn't run the test suite.
- I didn't change any code.

**Suggested fix (not applied):** revert line 353 to `min(timestamps)`, correct the commit-message and comment mismatch, and add a test for the escalated-then-stable sequence. Costs already written with the bad cut-off would need a backfill, which is a decision for the finance team.

----- next turn -----

The cost fix is in and the regression test is in place. The cost tests all pass against local PostgreSQL: 20 passed with `python -m pytest tests/case_cost`.

**Changes**
- `src/dispatch/case_cost/service.py:353`: the cut-off is back to `min(timestamps)`. The comment above it already described the earliest-milestone behavior, so I left it as is.
- `tests/case_cost/test_case_cost_service.py`: new test `test_case_cost_stops_at_first_milestone_when_escalated_then_stable`. It sets up an assignee who joined 3 hours ago, a case escalated 2 hours ago and stable 1 hour ago. The expected time is 1 hour at the assignee multiplier, meaning cost stops at escalation.

**Verification**
- With the buggy `max` restored temporarily, the new test fails. With the fix it passes. I then restored `min`.
- I ran only the case-cost test module, not the full suite.

**Not done**
- I didn't commit anything.
- Costs already written with the bad cut-off are not corrected. Backfilling them is a decision for the finance team.
- The test file showed a notice that it changed on disk after I read it. The git diff contains only my additions, so I think nothing else was touched, but you may want to check whether someone else is editing that file.

----- next turn -----

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. When either is `None`, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's `calculate_cases_response_cost` catches the error per case, logs it, and skips that case, so those cases got no cost. The log has 708 of these from Sep 8 onward. I couldn't identify which projects have the null values, because the logs don't name them and the database isn't available to me.

**Fix:**
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` now falls back to the defaults for either value that is `None`.
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now module constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and the Pydantic schema use them, so the fallback and the model can't drift apart.
- `tests/case_cost/test_case_cost_service.py`: new test `test_get_hourly_rate_uses_project_defaults_when_values_missing`. It covers each value missing alone, both missing, and both set.

**Verification:** `python -m pytest tests/project tests/incident_cost tests/case_cost` passes, 42 tests. Ruff isn't installed in this environment, so I couldn't lint.

**Things to know:**
- The `min` fix from earlier is still in place in the same file.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I didn't change it because you asked about the case cost job. It will hit the same error for incidents on projects with null values.
- The traceback in the log came from the installed package under `/usr/local/lib/python3.11/site-packages`, not from this checkout. I assumed it matches this code, since the failing line is identical.
- Nothing is committed.

----- next turn -----

Here's the recap for the incident report.

**Incident: inflated case response costs (from Sep 3) and skipped cases (from Sep 8)**

1. **Inflated costs.** Commit `20f33137` (Sep 2) changed the case-cost cut-off from the earliest milestone (`min`) to the latest (`max`) of `stable_at`, `escalated_at` and `closed_at`. Once a case was escalated, its cost froze at the escalation time. When the case was later marked stable, the cut-off moved to `stable_at`, so the cost jumped. Case 5363 went from 2261 to 6241 on Sep 9 this way. The change reached production in `main-65f7df6e` on Sep 2 at 18:14 UTC. The first flagged inflation was case 5284 on Sep 3 at 11:20 UTC.
2. **Hourly TypeError.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no null check. Projects with no annual employee cost set raised a TypeError, and the scheduler logged it and skipped the case. The log shows 708 of these from Sep 8 onward.

**Fixes (not committed):**
- `src/dispatch/case_cost/service.py`: the cut-off is back to `min`. `get_hourly_rate` falls back to the project model defaults for a missing value.
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now shared constants used by the column defaults, the Pydantic schema and the fallback.
- Tests: `test_case_cost_stops_at_first_milestone_when_escalated_then_stable` fails with the `max` change and passes with the fix. `test_get_hourly_rate_uses_project_defaults_when_values_missing` covers each missing value.
- `python -m pytest tests/project tests/incident_cost tests/case_cost`: 42 passed.

**Open items:**
- Costs written with the bad cut-off, and cases skipped since Sep 8, aren't corrected. The finance team will need a backfill.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I didn't change it.
- I couldn't explain the 3425 → 1243 drop for case 5363 on Sep 5.
- I couldn't identify the projects with null settings, because the logs don't name them.
- Ruff wasn't available, so the changes weren't linted.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost