**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02). It changed one line in `get_participant_role_time_seconds`, in `src/dispatch/case_cost/service.py` (about line 353):

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds `stable_at`, `escalated_at` and `closed_at`. It is the cut-off after which a participant's role time stops accruing. The old code stopped the clock at the earliest of those events, and the comments in the function still describe that behaviour ("earliest relevant timestamp", "before the case was marked as stable or closed"). The new code stops it at the latest event instead.

This only affects cases that have more than one of those timestamps. Case 5363 shows how:
- **Escalation:** around 2025-09-05 16:20Z the case was escalated, and its classic cost stopped growing at $2,261. That is a frozen cut-off, so it was the escalated timestamp.
- **Stable:** on 2025-09-09 12:20Z it was marked stable. The cut-off moved from the escalation time to the stable time, so about four more days of role time were counted. The cost jumped to $6,241 (+176%).

The same pattern shows up in the other cases the sync flagged (cost and stable timestamps behind the rest are inferred from the sync log, not checked against Dispatch):

| Case | Date flagged | Cost change |
|---|---|---|
| 5284 | 09-03 | $3,331 → $8,804 |
| 5327 | 09-05 | $2,244 → $5,539 |
| 5264 | 09-08 | $3,285 → $11,987 |
| 5363 | 09-09 | $2,261 → $6,241 |
| 5406 | 09-12 | $1,975 → $4,945 |

The cost values in Dispatch itself are wrong, not just the warehouse copy. The sync is only reporting what the API returns.

**Deploy that shipped it:** the first deploy to production containing the commit was image `registry.example.com/dispatch:main-65f7df6e`.
- **What it was:** the db-upgrade job started at 2025-09-02 18:14:09Z. Web and scheduler were rolled over by 18:15:54Z.
- **Why it carries the fix:** the commit was authored 16:29Z that day, and `20f33137` is an ancestor of `65f7df6e`.
- **First flagged jump:** case 5284 at 2025-09-03 11:20Z, the first after this deploy. No case was flagged before it.
- **Later deploy:** `main-51546e13` on 2025-09-04 16:52Z also includes the change, but it is not the first.

**Ruled out:**
- **Cost-sync upgrade:** `case-cost-sync` went from 1.4.2 to 1.5.0 on 2025-09-01 10:20Z, a day before the deploy. No cost jumps appear until after the Dispatch deploy.
- **Earlier deploy:** `main-3e0445ff` on 08-27 predates the commit.
- **Scheduler restart:** the one on 09-10 reused the same image.
- **Rates and cost models:** the case cost jumps trace to the cut-off timestamp, not to rates or models.

I haven't changed any code. The fix would be to revert to `min(timestamps)`. If the "latest" behaviour was intended, the comments need to say so and finance has to be told. Either way, every case that became stable or escalated since 09-02 needs its cost recalculated, and the warehouse rows need re-syncing.

----- next turn -----

I fixed the bug and added a regression test. All 20 tests in `tests/case_cost` pass with the fix. I didn't run the rest of the suite or commit anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `max(timestamps)` is back to `min(timestamps)`. The cost cut-off is again the earliest of `escalated_at`, `stable_at` and `closed_at`.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py` sets up a case escalated 8 hours in, then stable and closed later. It asserts the role time is cut off at the escalation. This is the shape of case 5363.
- **Check:** with the fix stashed, the new test fails and the other 19 pass. The existing stable-only test never exercised more than one timestamp, which is why it missed the change.

**Still to do:** the wrong costs already stored in Dispatch, and the rows the finance sync copied into the warehouse, will not correct themselves. Cases that went stable or escalated since the 2025-09-02 deploy need their costs recalculated, and finance needs to re-sync those rows.

----- next turn -----

The scheduler's TypeError is fixed, and the cases with missing project settings now get a cost. All 22 tests in `tests/case_cost` pass. I didn't run the rest of the suite or commit anything.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both are nullable columns on `Project`, and some projects have NULL for `annual_employee_cost`. That gives `unsupported operand type(s) for /: 'NoneType' and 'int'`, which matches all 708 errors in `scheduler.log`. The traceback runs through `calculate_case_response_cost_new` to `get_hourly_rate`, so the cases in those projects never got a cost. The column defaults (50000 and 2080) only apply when nothing is passed, not when NULL is stored explicitly. Why those projects have NULL, and why it only showed up from September 8, I haven't determined, and the logs don't say. The 708 errors are all the "None divided by int" form, so `business_year_hours` was never the missing one in this log.

**Fix:** when either value is `None`, `get_hourly_rate` now falls back to the `Project` model's column default (50000 annual cost, 2080 hours). It reads the default from the model, so it can't drift from the schema.

**Tests**, both in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_settings_use_model_defaults` covers either value missing, or both.
- `test_calculate_case_response_cost__project_without_cost_settings` checks that a case in a project with neither setting gets a positive classic cost.

With the `src/` fix stashed, these two tests fail, along with the earlier cut-off regression test, which is expected since the stash also removes that fix.

- **Not covered:** `get_hourly_rate` in `src/dispatch/incident_cost/service.py` has the same unguarded division, so incident costs would fail the same way for such projects. I left it alone since you asked about the case cost job.
- **Not covered:** a value of 0 for business year hours would still raise a `ZeroDivisionError`. I only treated missing values as unset.

----- next turn -----

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`, in `src/dispatch/case_cost/service.py`. The cost cut-off for a case's participant role time moved from the earliest of `escalated_at`, `stable_at` and `closed_at` to the latest. A case escalated and later marked stable (or closed) therefore kept accruing cost after the escalation. Case 5363 went from $2,261 to $6,241 this way on 2025-09-09.
- **Deploy:** the first production deploy containing it was image `main-65f7df6e`. It started at 2025-09-02 18:14Z and was fully rolled out by 18:15:54Z. The later `main-51546e13` deploy (09-04) also carries the change, but it wasn't the first.
- **First inflated case:** case 5284 on 2025-09-03 (sync at 11:20Z, $3,331 → $8,804). No sync before it shows a comparable jump after the deploy. This rests on the sync log. A smaller inflation under my 400-dollar filter, or one the sync didn't log, could in principle be earlier.
- **Status:** fixed by reverting to `min`, with a regression test. Costs already stored in Dispatch and the warehouse rows still need recalculating and re-syncing for cases that went stable or escalated since 2025-09-02.

**Hourly TypeError**
- **Cause:** `get_hourly_rate` divided a NULL `annual_employee_cost` by `business_year_hours` for some projects. That produced 708 errors in `scheduler.log` and left those cases with no cost. I did not find out why those projects have NULL, or why it only started on September 8.
- **Status:** it now falls back to the `Project` model defaults (50000 and 2080), with tests. `incident_cost/service.py` has the same unguarded division and was left unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost