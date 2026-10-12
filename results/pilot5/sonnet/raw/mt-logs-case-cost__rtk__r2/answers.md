**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02). It changed one line in `get_participant_role_time_seconds`, in `src/dispatch/case_cost/service.py`:

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

The `timestamps` list holds `stable_at`, `escalated_at` and `closed_at`. The code uses it as the point where a participant's time in a role stops counting. Taking the earliest stopped the clock when the case first left active work. Taking the latest lets the clock run until the last of those timestamps, or until now when the role was never renounced. Those timestamps are never cleared, so any case with more than one of them gets charged for time it previously wasn't.

**Why it hits Stable cases:** `calculate_cases_response_cost` recomputes cases in new, triage and stable status every hour (`src/dispatch/case_cost/scheduled.py`). A stable case is only skipped once its cost row was updated after `stable_at`. So the next hourly recalculation after the deploy re-prices those cases with the new cut-off, and the finance sync copies the result. The comment above the code still says "earliest relevant timestamp", so the change contradicts its own documentation.

**Which deploy shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, deployed on 2025-09-02 at about 18:14 to 18:15 UTC.
- `events.log` shows the `dispatch-db-upgrade-65f7df6e` job pulling the image at 18:14:25. It then shows the scheduler replica set scaling down at 18:14:41 and the new one scaling up at 18:15:09, with the web pods rolling alongside.
- `65f7df6e` is the first deployed commit after `20f33137` on main, so that image includes it. The previous production image was `main-3e0445ff` (2025-08-27), which does not.
- The next deploy, `main-51546e13` on Sep 4 at 16:52, only carried the Slack canvas change. It isn't the cause, because the first jump predates it.

**Timeline from `cost-sync.log`:**
- From 08-25 to 09-02 there are no "flagged for review" warnings.
- The first one is 09-03 11:20, and every flagged case is Stable:

| Case | Flagged at | Change |
|---|---|---|
| 5284 | 09-03 | 3331 → 8804 |
| 5327 | 09-05 | 2244 → 5539 |
| 5264 | 09-08 | 3285 → 11987 |
| 5363 | 09-09 12:20 | 2261 → 6241 |
| 5406 | 09-12 | 1975 → 4945 |

- Case 5363 had been frozen at 2261 since 09-05 16:20 and jumped on 09-09 at 12:20.

**Things I ruled out:**
- **Finance job version:** case-cost-sync went from 1.4.2 to 1.5.0 on 09-01 10:20, before the first jump. It moved from 50 to 100 cases per page and has no flagged jumps until after the deploy.
- **Database outage:** the scheduler errors on 09-06 03:54 are a database connection refusal and unrelated.
- **Hourly rate error:** from 09-08 15:55 the scheduler logs `annual_employee_cost` being None in `get_hourly_rate` (`service.py:118`). That is a separate bug, and it shows up only in the new cost model's calculation, which crashes. It doesn't explain the inflated classic costs.

**What I couldn't confirm:** the logs don't contain case status history or the actual `stable_at`, `escalated_at` and `closed_at` values. So I can't say which later timestamp pushed each case's cut-off out. The code change, the deploy timing and the Stable-only pattern all fit, but checking the timestamps for cases 5363 and 5284 in the database would confirm it.

**Fix to consider (no code changed yet):** revert to `min`, or compute the cut-off from the case's current status. Then recompute the costs of the affected stable cases and re-sync the finance warehouse, since it holds inflated values for every case recalculated since 09-02.

----- next turn -----

I reverted the cut-off to `min(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). I also added a regression test. Nothing is committed yet.

The test is `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets up a participant still in their role and a case that was marked stable, then escalated, then closed. It asserts that only the time up to `stable_at` is counted. With the `max` code it fails, and with the fix it passes, so it would have caught the original change. All 20 tests in `tests/case_cost` pass.

I ran only the case-cost tests, not the full suite.

Fixing the code doesn't repair the data. The finance warehouse still holds inflated costs for every case recalculated since the Sep 2 deploy. Stable cases won't be recalculated automatically, because the scheduler skips them once their cost row was updated after `stable_at`. So after deploying, the affected cases need a one-off recalculation. Then the finance team needs to re-sync, or backfill from Sep 2 onward.

----- next turn -----

The hourly case-cost job's TypeError came from projects with no `annual_employee_cost` or `business_year_hours` set. I've fixed it, so those cases now get a cost, and added a test. The case-cost tests pass (21 tests). I haven't run the full suite.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divided `project.annual_employee_cost` by `project.business_year_hours`. Both columns on `Project` are nullable, and the `default=50000` and `default=2080` only apply when a row is first inserted. A project that had either value cleared later therefore holds NULL, and the division raised `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The Pydantic project model also allows `None` for both fields. The scheduler catches the error per case, so each affected case was skipped and re-logged every hour. The cost-sync logs show these cases not updating.

I couldn't see which project it is. The scheduler log doesn't name it, and the first error is 2025-09-08 15:55, which was not a deploy day. My guess is a project edit around then that cleared one of the values.

**Fix:** `get_hourly_rate` now uses the `Project` model's column default (50000 or 2080) for whichever value is `None`. It reads the default from the column definition rather than repeating the numbers.

**Test:** `test_get_hourly_rate__missing_project_values_use_model_defaults` covers both values missing, only the hours missing, and only the cost missing.

**Two things to check:**
- **Data:** I didn't touch the project settings. The project that lost its values still has NULLs, and it will quietly use the defaults. If its real rates differ from 50000 and 2080, the costs will be wrong, so it is worth setting them properly.
- **Incident costs:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division. It didn't log errors in this period, but it will fail the same way. I left it alone since you only asked about cases. Say if you want it fixed too.

----- next turn -----

## Recap

**Cost inflation.** Commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function decides when a participant's time in a role stops counting.

- **Effect:** the cut-off moved from the earliest of `stable_at`, `escalated_at` and `closed_at` to the latest. Stable cases that also carried a later timestamp kept accruing cost, and the hourly scheduler job recomputed them.
- **Shipped:** the change went to production in image `main-65f7df6e` on 2025-09-02 at about 18:14 UTC. Production had been running `main-3e0445ff`, which doesn't contain it.
- **Timeline:** the first inflated cost I can see is case 5284 on 2025-09-03 at 11:20 UTC, 3331 → 8804, flagged by the finance job. No case had a rise over 400 between 2025-09-02 and that point. Earlier inflation under the 400 cutoff isn't ruled out.
- **Status:** fixed by reverting to `min`, and a regression test was added. The warehouse still holds inflated values from 09-02 onward, so it needs a recalculation and re-sync.

**TypeError since September 8.** `get_hourly_rate` divided a project's annual employee cost by its business year hours. Both are nullable columns, and their defaults only apply on insert.

- **Setting:** the error text was `'NoneType' and 'int'`, so the `None` was the dividend, which is `annual_employee_cost`. A missing `business_year_hours` would have produced `'int' and 'NoneType'`. The 708 tracebacks in the scheduler log all show the first form.
- **Status:** fixed. A missing value now falls back to the `Project` model's column default (50000 for the cost, 2080 for the hours), with a test.
- **Open question:** I couldn't tell which project lost its setting. If its real rates differ from the defaults, its case costs are still wrong.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost