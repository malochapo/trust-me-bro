**Root cause: commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02 09:29:50 -0700). The deploy that shipped it was `main-65f7df6e` on 2025-09-02 at about 18:14Z.**

I couldn't tie the Sep 9 jump to a specific database event, because the logs have no per-case state. The mechanism below is read from the code and the log pattern.

**The change**

In `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:~353`), the one-line change was:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

`timestamps` holds `stable_at`, `escalated_at` and `closed_at`. The code comment above it still says "Determine the **earliest** relevant timestamp for cost calculation cut-off."

Costing stops at the first time the case left active response, so `min` is correct. With `max`, a case that has more than one of these timestamps is costed up to the latest one. Cases with only one timestamp are unaffected, which is why only some stable cases are hit. Cost therefore keeps accruing past the stable point and is overstated. The hourly job `calculate_cases_response_cost` writes these values to the DB, and the API serves them to the finance team's sync.

**Evidence from the logs**

- **Case 5363's cost was flat, then jumped.** Its classic cost froze at 2261 from 2025-09-05 16:20 to 2025-09-09 11:20, then went 2261 → 6241 at 2025-09-09 12:20 (`cost-sync.log:8911`). That is the figure you quoted.
- **Other cases show the same pattern.** `costsync.checks` flagged four more "Stable" security cases: 5284 (3331 → 8804, Sep 3), 5327 (Sep 5), 5264 (3285 → 11987, Sep 8) and 5406 (Sep 12). Before Sep 2 the sync log has no such flags; the first is on Sep 3.
- **The first deploy containing the commit:** I checked ancestry with git, and `20f33137` is in `65f7df6e` and `51546e13` but not in `3e0445ff`. The events log shows:
  - `3e0445ff` was deployed on Aug 27 and does not contain the bug.
  - `65f7df6e` was deployed on Sep 2 (db-upgrade job at 18:14:09Z, web and scheduler rolled by 18:15Z). This is the first deploy containing the bug.
  - `51546e13` was deployed on Sep 4 at 16:52Z and still contains it.
- **The first flag came a day after the deploy.** The flags start on Sep 3, once recalculation of stable cases began using the new cut-off.

**Ruled out**

- **cost-sync 1.4.2 → 1.5.0 (Sep 1 10:20Z):** it only changed the page size from 50 to 100, and it was deployed before the bug.
- **DB connection-refused errors on Sep 6 03:54 and the `unsupported operand type(s) for /` errors:** these don't explain the jumps. The second looks like a separate problem, a missing hourly rate for a project, which I didn't investigate.
- **Hourly rates and cost models:** the code history for them has no recent change, as you said.

**Fix and cleanup (not done, as you asked)**

- Revert `max` to `min`.
- After the fix, the scheduler skips stable cases whose cost was updated after `stable_at`. Inflated costs already stored for those cases won't be corrected automatically, so they need a forced recalculation, and finance needs to re-sync the affected rows.
- To find the affected rows, look for cases with `stable_at` plus a later `escalated_at` or `closed_at`.

----- next turn -----

I've reverted `max` to `min` in `src/dispatch/case_cost/service.py`, so the cost cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at` again. I haven't committed anything.

I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It has two cases:
- A case that went stable, then escalated, then closed must be costed only up to `stable_at`.
- A case that was escalated first and went stable and closed later must be costed only up to `escalated_at`.

With the fix, all 20 tests in `tests/case_cost` pass. With the source change stashed (the buggy `max`), the new test fails and the other 19 pass, so the existing tests would not have caught it. I ran only `tests/case_cost`, not the full suite.

The costs already stored for affected cases will not fix themselves. The hourly job skips stable cases whose cost was updated after `stable_at`, so those cases need a forced recalculation. Finance also needs to re-sync the affected rows. The affected cases are those with `stable_at` plus a later `escalated_at` or `closed_at`, including 5284, 5327, 5264, 5363 and 5406.

----- next turn -----

The TypeError is fixed: cases whose project has no annual employee cost or no business year hours now get a cost. The 22 tests in `tests/case_cost` pass, and with the source changes stashed the two new tests fail (along with the earlier min/max test), so they catch the bug. I ran only that directory, not the full suite, and haven't committed.

**Cause.** `get_hourly_rate` (`src/dispatch/case_cost/service.py`) divides `project.annual_employee_cost` by `project.business_year_hours`. For some projects `annual_employee_cost` is NULL. The `default=50000` on the column only applies on insert, and `ProjectBase` accepts `None` for both fields, so a project saved with no value stores NULL.

The scheduler log shows 1,416 identical errors, `unsupported operand type(s) for /: 'NoneType' and 'int'`, from the first at 2025-09-08 15:55 to the end of the log. Each one comes from `calculate_case_response_cost_new` in the hourly job. The job catches the exception per case, so those cases are skipped and keep a stale or missing cost every hour.

**Open question.** I couldn't tell from the logs what put the NULL in on Sep 8. It was presumably a project edit, but that is a guess.

**Fix.** A missing `annual_employee_cost` or `business_year_hours` now falls back to `Project.annual_employee_cost.default.arg` or `Project.business_year_hours.default.arg` (50000 and 2080). It reads the model's defaults rather than repeating the numbers.

**Tests added** to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_values_use_model_defaults`: both missing, only one missing, and the other one missing.
- `test_calculate_case_response_cost__project_without_cost_settings`: a full case cost calculation with both values NULL.

**Not changed.**
- **Incident costs:** `src/dispatch/incident_cost/service.py:131` has an identical `get_hourly_rate` with the same crash for incidents. I left it alone since you asked about cases; say if you want it fixed too.
- **Project data:** the NULLs are still in the project data. Backfilling them, or stopping the project form from saving null, would stop other code from hitting them.
- **Stale costs:** cases skipped since Sep 8 will get a cost at the next hourly run. If finance needs a one-time correction, they should re-sync those rows afterwards.

----- next turn -----

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