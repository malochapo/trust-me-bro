**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, Sep 2 2025). It was first deployed to production in image `main-65f7df6e` on Sep 2 at about 18:14–18:15Z. I couldn't see the database timestamps for case 5363, so how the change produces that case's jump is inferred, not observed.

**The change.** In `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:~353`), one line changed from `min(timestamps)` to `max(timestamps)`. Those timestamps are `stable_at`, `escalated_at` and `closed_at`. The result is the point where a participant's time, and therefore cost, stops accruing.
- Before, the cut-off was the earliest of those timestamps. Cost froze when the response effectively ended.
- Now it is the latest of them. If a case has more than one of those timestamps set, cost keeps accruing up to the latest one.
- The scheduler's hourly `calculate_cases_response_cost` job recalculates stable cases. It then writes the larger amount, which the API returns and case-cost-sync copies into the warehouse.

**Evidence from the logs**
- **Jumps in `cost-sync.log`.** I parsed every `costsync.diff` line, 6,846 in total. The only large upward jumps are five cases, all Stable, and none occurred before the deploy:

| Case | Date | Classic cost |
|---|---|---|
| 5284 | Sep 3 | 3331 → 8804 |
| 5327 | Sep 5 | 2244 → 5539 |
| 5264 | Sep 8 | 3285 → 11987 |
| 5363 | Sep 9 | 2261 → 6241 |
| 5406 | Sep 12 | 1975 → 4945 |

- **Quiet before the deploy.** From Aug 25 to Sep 3 11:20, no case was flagged. The first jump came about 17 hours after the scheduler restarted on `main-65f7df6e`.
- **Normal drops are unrelated.** The many large drops are the existing "8 working hours per day after 24 hours" compression, not part of this problem.
- **Case 5363 stayed flat.** Its cost sat at 2261 from Sep 5 16:20 until Sep 9 12:20, then jumped to 6241. That looks like a case whose cost was frozen at an earlier timestamp and is now extended to a later one.

**The deploy.** `events.log` shows the rollouts in order:

| Image | When | Contains `20f33137`? |
|---|---|---|
| `main-3e0445ff` | Aug 27 17:03Z | No (the commit is newer) |
| `main-65f7df6e` | Sep 2 18:14Z (db-upgrade job, then web and scheduler pods) | **Yes, first deploy** |
| `main-51546e13` | Sep 4 16:52Z | Yes |

Both later images are descendants of `20f33137`, so a rollback to `3e0445ff` or a revert of the `max` line would undo it. The scheduler pod restart on Sep 10 reused `main-51546e13` and didn't change anything.

**Ruled out**
- **case-cost-sync 1.4.2 → 1.5.0** went live Sep 1 at 10:20Z. It changed the page size from 50 to 100. No jumps appeared for two more days, and the jumps match the Dispatch deploy.
- **Hourly rates and cost models** didn't change. The jumps are in the classic model only, and I saw no config change in the logs.

**A separate problem.** Since Sep 8 15:55, the scheduler has logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate`. `project.annual_employee_cost` is `None`. The errors grow from 9 on Sep 8 to about 150 a day by Sep 12–14. Those cost updates fail, which may leave some costs stale, so it's worth a separate look.

**Before you fix it:** check the DB for case 5363. Compare `stable_at`, `escalated_at` and `closed_at`, and see whether the 6241 corresponds to the latest of them. Then decide whether to revert the line or recompute the affected warehouse rows, which is every Stable case with more than one of those timestamps since Sep 2 18:15Z. I haven't changed any code.

----- next turn -----

I reverted the cut-off to the earliest status timestamp, and the new test fails without the fix and passes with it. All 20 tests in `tests/case_cost` pass with the fix. I haven't committed anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` uses `min(timestamps)` again instead of `max(timestamps)`. This undoes `20f33137`.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a stable case with `escalated_at` three hours ago, `stable_at` two hours ago and `closed_at` one hour ago. The participant's role began four hours ago and is still active. It asserts that only one hour of time is counted, from the role's start to the earliest timestamp.
- **Why the old tests missed it:** the existing stable-time test only set `stable_at`, so `min` and `max` gave the same answer.

**Still to do:** this only stops new overcounting. The warehouse rows written since Sep 2 18:15Z are still inflated.
- **Cases:** the five I found were 5284, 5327, 5264, 5363 and 5406. Others may be affected too.
- **Why they may not correct on their own:** the scheduler's skip-if-already-updated rule leaves Stable cases alone once their cost was written after `stable_at`. Their stored amounts may not recompute. They probably need a one-off recalculation, then a re-sync.

I didn't touch the separate `annual_employee_cost` is `None` error from my earlier report.

----- next turn -----

The TypeError is fixed. `tests/case_cost` passes (21 tests), and the new test fails without the fix. Nothing is committed.

**Cause.** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. For some projects one or both of those are `None`.
- **Why they are `None`.** The project API schema (`ProjectBase`) allows null for both fields. `project_service.create` passes whatever it receives to `Project(...)`. An explicit null overrides the column defaults (50000 and 2080), so the project is stored with nulls.
- **Which project.** A new `fraud` project first shows up in the scheduler log on Sep 8 at 14:54. Its cases are the ones that fail every hour from 15:55 on, with the `unsupported operand type(s) for /: 'NoneType' and 'int'` error. I inferred it is the project with the nulls; the logs don't show its values.
- **Effect.** Those cases get no cost at all. The error aborts the calculation, so they have no row in the warehouse.

**Fix.** `get_hourly_rate` in `src/dispatch/case_cost/service.py` now falls back to the `Project` model's column defaults for whichever value is missing. It reads them from the model, so the numbers aren't duplicated.

**Test.** `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers three cases:
- both values missing, which gives 25;
- only the cost missing;
- only the hours missing.

- **Same bug in `incident_cost`.** `incident_cost/service.py:133` has the same division and will fail the same way for that project's incidents. I left it alone since you asked about cases. Say if you want the same fix there.
- **Root source of the nulls.** I didn't change the schema or project creation. New projects can still be saved with nulls, and the fallback now covers them.

----- next turn -----

That +230 on case 5323 is ordinary growth from a participant joining, not this bug, so the first inflated case is 5284 on Sep 3.

## Recap

**Cost inflation.**
- **Cause.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the point where a case's response cost stops accruing, using `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has more than one of those timestamps keeps accruing cost up to the latest one instead of stopping at the earliest.
- **Deploy.** The change first reached production in `main-65f7df6e` on Sep 2 at about 18:14Z. `main-51546e13` on Sep 4 also contains it.
- **First inflated case.** Case 5284 was inflated on Sep 3 (3331 → 8804 at 11:20Z). Before the deploy, nothing was flagged. The other flagged cases were 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12).
- **Fix.** I reverted the line to `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. It fails without the fix.
- **Not yet done.** Warehouse rows written since Sep 2 18:15Z are still inflated. Stable cases whose cost was already updated after `stable_at` won't be recomputed by the scheduler, so they need a one-off recalculation and re-sync.

**Hourly TypeError.**
- **Cause.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`, and one was `None` for the new `fraud` project. The project API allows null for both, and an explicit null bypasses the column defaults (50000 and 2080). The scheduler first logged the error on Sep 8 at 15:55. I inferred `fraud` is the affected project from the log timing, not from its stored values.
- **Fix.** `get_hourly_rate` now falls back to the `Project` model defaults for whichever value is missing, with a test.
- **Open item.** `incident_cost/service.py:133` has the same division and would fail the same way. I left it unchanged.

Both fixes are uncommitted in the working tree.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost