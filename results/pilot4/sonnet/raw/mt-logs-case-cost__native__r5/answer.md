The root cause is `20f33137` flipping `min` to `max` in the cost cut-off in `src/dispatch/case_cost/service.py`. It shipped in the `main-65f7df6e` deploy.

**Recap**

- **Inflated costs.** `get_participant_role_time_seconds` is supposed to stop costing a participant at the earliest of `stable_at`, `escalated_at` and `closed_at`. The change used `max`, so a case with several of those timestamps kept accruing cost up to the latest one. The hourly job saved the inflated values, and the finance sync copied them into the warehouse. Case 5363 went from $2,261 to $6,241 on Sep 9 this way.
- **Deploy.** The commit was authored on Sep 2 at 09:29 -0700. The first production deploy that contains it is `main-65f7df6e`, rolled out on Sep 2 at about 18:14Z. The previous image, `main-3e0445ff`, does not contain it. `main-51546e13` (Sep 4) still did until the fix.
- **First inflated case.** The first flagged jump is case 5284 on Sep 3 at 11:20Z (3331 → 8804). I used that as the first inflated date. The sync's checks only flag increases of roughly +100% or more, so smaller inflations earlier that day could exist but I can't see them in the logs.
- **TypeError.** From Sep 8 15:55 the hourly job logged `NoneType / int` for some cases. `get_hourly_rate` divided a NULL `annual_employee_cost` by `business_year_hours`. Those cases were skipped every hour.
- **Fixes.**
  - Reverted `max` to `min`, with a regression test.
  - Made `get_hourly_rate` fall back to the project model defaults (50000 and 2080), with tests. `tests/case_cost` passes (22 tests); I did not run the full suite. Nothing is committed.
- **Still open.**
  - Stored inflated costs need a forced recalculation and a re-sync by finance.
  - `incident_cost/service.py` has the same `get_hourly_rate` crash.
  - I don't know what put the NULL in the project on Sep 8.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost