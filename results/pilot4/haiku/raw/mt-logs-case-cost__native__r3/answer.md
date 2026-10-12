The recap is below. The six lines at the end are the values you asked for. `FIRST_INFLATED` is the first inflated value in the cost-sync log, which I checked against every diff from the deploy onward. The Dispatch database itself has no timestamps I could check, so an earlier inflation can't be ruled out.

## Recap

**Cost bug.** Commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function picks the time at which a participant's role stops accruing cost, from `stable_at`, `escalated_at` and `closed_at`. The original `min` stops at the earliest of these, which matches the function's comment. `max` stops at the latest, so a case that was escalated and later marked stable kept accruing cost for the escalated→stable interval. The scheduler recalculates a stable case once it becomes stable, so the jump appears at that point. Case 5363 went from $2,261 to $6,241 on Sep 9 this way.
- Shipped in `main-65f7df6e`, rolled out to the scheduler on Sep 2 at 18:15 UTC. The scheduler has run images containing this change since then, including the current `main-51546e13`.
- Fix: `min` restored. Regression test `test_case_cost_stops_at_earliest_status_timestamp` fails on the buggy code (7200 vs 3600 seconds) and passes after the fix.

**Hourly TypeError.** Since Sep 8, the hourly job has logged `unsupported operand type(s) for /: 'NoneType' and 'int'` for some cases. `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. A project saved with NULL for `annual_employee_cost` made the numerator `None`. The per-case handler skipped those cases, so they never got a cost.
- Fix: a missing value now falls back to the project model defaults, 50000 and 2080. Tests `test_get_hourly_rate_falls_back_to_project_defaults` and `test_case_cost_with_unset_project_values` cover this.
- I could not identify which project was saved with NULL from the logs.

**Test results.** The full suite gives 364 passed, 4 skipped, and 8 failures in `tests/ai`, `tests/database` and `tests/entity`. The same 8 fail on the unmodified commit.

**Not done:**
- Nothing is committed or deployed yet.
- Stable cases already inflated since Sep 2 keep their wrong values until someone backfills them. I haven't designed or run that.
- `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` without the fallback.
- A `business_year_hours` of 0 still raises `ZeroDivisionError`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost