**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", 2025-09-02, Jordan Lee). It changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

`timestamps` holds `stable_at`, `escalated_at` and `closed_at`. The code's own comment says it picks "the earliest relevant timestamp for cost calculation cut-off". Before the change, response cost stopped accruing at the first of those events. Now it keeps accruing until the last one. The commit title says "latest", so the change looks deliberate, but it contradicts the comment and the cost model. The change was also tied to no cost-model or rate change.

**Fit with your example, case 5363:**
- `costsync.diff` shows the classic cost rising about $145 per hour until 2025-09-05 16:20, reaching $2,261.
- It then stayed flat for about four days, which is the old behaviour: cost frozen at the first status event.
- At 2025-09-09 12:20 the case was marked stable. `stable_at` is now later than the earlier timestamp, so `max()` extends the cut-off and the cost jumped to $6,241 (+176%). This is my inference from the cost pattern. I haven't checked the case's `escalated_at` and `stable_at` values directly.
- The same pattern shows on cases 5284, 5327, 5264 and 5406. `case-cost-sync` flagged all of them with `costsync.checks` warnings of +147% to +265%, and every flagged case was in `Stable` status.

Cost-sync itself is not at fault. It stayed at version 1.4.2 and the `case-cost-sync:1.4.2` image never changed. It copied what the Dispatch API returned.

**The deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z.
- At 18:14:09Z the `dispatch-db-upgrade-65f7df6e` job pulled the image.
- The `dispatch-web` rollout to the `zrhzjwmzrh` replica set started at 18:14:36Z.
- The `dispatch-scheduler` rollout to the `qdd74fpnsl` replica set finished at 18:15:09Z.

The image tag names the HEAD commit, `65f7df6e`. `20f33137` was committed about seven hours earlier (09:29 PDT, 16:29Z) and is an ancestor of it. The previous production image, `main-3e0445ff`, was deployed on 2025-08-27 and predates the commit. The first flagged jump came on 2025-09-03, the day after the rollout. I found no flagged jumps before the deploy, but I only looked at the five flagged warnings and a quick scan of the `costsync.diff` lines. The log is full of normal hourly increases, so I wouldn't treat the "none before" claim as exhaustive.

**Not the cause:**
- The 2025-09-04 deploy (`main-51546e13`) contains the same bug, since it is a descendant. It did not introduce it.
- The 2025-09-10 scheduler pod restart did not introduce it either.
- The readiness-probe warnings in `events.log` are unrelated.

**What still needs fixing:** the warehouse holds inflated costs for every case that reached stable, escalated or closed status since 2025-09-02 18:15Z. Reverting the line stops new inflation. Those cases will probably need to be recomputed and re-synced.

I haven't changed any code.

----- next turn -----

I reverted the one-line change in `src/dispatch/case_cost/service.py`, so the cost cut-off is back to `min(timestamps)`, the earliest of `stable_at`, `escalated_at` and `closed_at`. I added a regression test and nothing is committed.

The test is `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds an active participant role on a case that was escalated, then marked stable, then closed. It asserts the role's time runs only up to the escalation timestamp.

I ran `python -m pytest tests/case_cost`:
- **With the fix:** all 20 tests pass.
- **With the fix stashed (buggy `max()`):** the new test fails and the other 19 pass.

The existing `test_case_cost_stops_at_stable_time` didn't catch the bug because it only ever sets `stable_at`. With a single timestamp, `min` and `max` give the same answer.

Reverting the line only stops new inflation. The warehouse still holds inflated costs for cases that reached stable, escalated or closed status since the 2025-09-02 18:15Z deploy. Those will need a recompute and re-sync on the finance side, and the fix has to be deployed before that re-sync.

----- next turn -----

The TypeError is fixed, with a test. I did not check the test against the unfixed code, but without the fix it would hit the same `None / int` error. `python -m pytest tests/case_cost` passes (21 tests). Nothing is committed.

**Cause:** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns on `Project` are nullable, and the column default only applies when a row is inserted. A project with either value set to NULL therefore fails with `unsupported operand type(s) for /: 'NoneType' and 'int'`.

The scheduler log shows where it surfaces. The hourly `calculate_cases_response_cost` job calls `update_case_response_cost`, then `calculate_case_response_cost_new`, then `get_hourly_rate(case.project)`. The error is logged for each affected case on every run, so those cases never got a new-model cost. I couldn't tell from the logs which project has the NULLs or why it started on September 8. A project edit or import that cleared the fields is my guess, but I haven't verified it.

**Fix:** `get_hourly_rate()` now falls back to the `Project` model's column defaults (50000 and 2080) for whichever value is missing. It reads them from the column definition, so there is no second copy of the numbers. This is the same fallback `individual/service.py` already applies.

**Test:** `test_get_hourly_rate__unset_project_values_use_defaults` covers both values missing (rate 25), only the hours missing (rate 50) and only the annual cost missing (rate 50).

`incident_cost/service.py` has an identical `get_hourly_rate()` with the same bug. I left it alone because you asked about case costs. The fix there is the same, if you want it.

----- next turn -----

## Recap

**What happened:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. The cost cut-off therefore moved from the earliest of `stable_at`, `escalated_at` and `closed_at` to the latest. Once a case reached a later status, its cost resumed after being frozen. The fix is to revert that line, and a regression test covers it.

**Evidence:**
- **Cost jumps:** five cases show the pattern in `cost-sync.log` (5284, 5327, 5264, 5363, 5406). Each case's cost stopped changing for 3 to 10 days, then jumped after it moved to Stable.
- **Case 5363:** its cost was flat at $2,261 from 2025-09-05 until 2025-09-09 12:20, then jumped to $6,241.
- **Deploy:** the deploy is `main-65f7df6e`, rolled out 2025-09-02 around 18:14–18:15Z. `20f33137` is an ancestor of it and was committed about seven hours earlier. The earlier image `main-3e0445ff` predates the commit.
- **Not the cause:** `case-cost-sync` stayed at 1.4.2 throughout. The later `main-51546e13` deploy also carries the bug but didn't introduce it.

**Second problem (separate):** from 2025-09-08 the scheduler's hourly cost job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` for some cases.
- `get_hourly_rate()` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the numerator was `None` in the log.
- `get_hourly_rate()` now falls back to the project model defaults (50000 and 2080) for whichever value is missing, and a test covers it.
- `incident_cost/service.py` has the same unfixed function.

**Still open:**
- The warehouse still holds inflated costs for cases that reached stable, escalated or closed status after the deploy. They need a recompute and re-sync once the fix is deployed.
- I don't know which project has the NULL setting or why it started on September 8.
- The first inflated cost I can show is case 5284 at 2025-09-03 11:20Z. Smaller inflations before that would not stand out in the log, but I found no cost resuming after a freeze earlier than that.
- Neither fix is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost