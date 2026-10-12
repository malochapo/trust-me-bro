**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02). It changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`:

```python
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. The cost of a participant role is meant to stop at the first of those events, which is why the code comment says "earliest relevant timestamp". With `max`, it runs to the last one instead. Any case that has more than one of those timestamps now accrues extra hours. The `HOURS_IN_DAY` adjustment then scales those extra hours. I haven't reproduced the calculation. The attribution rests on the diff and the timing.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15 UTC.
- The `dispatch-db-upgrade-65f7df6e` job started at 18:14:09. The web pods and the scheduler (`dispatch-scheduler-qdd74fpnsl`, started 18:15:24) then moved to that image.
- `65f7df6e` is the first deployed commit after `20f33137`, so the fix is in that image.
- The previous deploy, `main-3e0445ff` on 2025-08-27, did not contain it.
- The next deploy, `main-51546e13` on 2025-09-04, only carried it forward.
- The scheduler is the process that recalculates case costs.

**Evidence in the logs:**
- `cost-sync.log` has no cost-spike warnings from 08-25 to 09-02. The first appears on 2025-09-03 11:20, and there are five by 09-12:

| Case | Cost change | Date |
|---|---|---|
| 5284 | 3331 → 8804 | 09-03 |
| 5327 | 2244 → 5539 | 09-05 |
| 5264 | 3285 → 11987 | 09-08 |
| 5363 | 2261 → 6241 | 09-09 |
| 5406 | 1975 → 4945 | 09-12 |

- Every flagged case is in `Stable` status. Before the fix, `min` stopped the cost clock when the case went stable. With `max`, cost keeps running toward the later escalated/closed timestamp, so it jumps when the case is marked stable.
- For case 5363, cost grew about $145 an hour up to $2,261. On 09-09 at 12:20 it jumped to $6,241 when the case was marked stable.

**Things I ruled out:**
- **case-cost-sync upgrade:** it went from 1.4.2 to 1.5.0 on 09-01 (page size 50 to 100). The diffs it logged stayed normal for the following day, so the upgrade isn't the cause.
- **Hourly rates and cost models:** I saw nothing that suggests they changed.

**Things I did not explain:**
- **Case 5363 drop:** it fell from 3425 to 1243 at 2025-09-05 09:20, with no deploy at that time. I didn't investigate it.
- **Unflagged cases:** the sync only flags increases above roughly 100%, so other affected cases may have smaller, unflagged inflation. Finance should recompute every case that has reached `Stable` since 09-02 18:15 UTC.

**Separate problem:** `calculate_cases_response_cost` has been raising `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate`. It happens at `project.annual_employee_cost / project.business_year_hours`, called from the new cost model path. There are 708 tracebacks, from 2025-09-08 15:55 to the end of the log. It points to a project with no annual employee cost set, which looks like a config change rather than a deploy. It doesn't inflate costs, but it may be stopping cost updates for the cases in the job's run.

I haven't changed any code. The fix is to revert `max` back to `min` in that line. After that, the affected cases need their costs recalculated and their warehouse rows re-synced.

----- next turn -----

I reverted the line to `min(timestamps)` and added a regression test. With the fix in place, all 20 tests in `tests/case_cost` pass. I didn't run the rest of the suite.

- **Fix:** `src/dispatch/case_cost/service.py` again cuts a participant's cost off at the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **New test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It gives a case `stable_at` 6 hours ago, `escalated_at` 3 hours ago and `closed_at` 1 hour ago. The role was assumed 10 hours ago and is still active. It asserts the role's time stops at `stable_at`. I checked that it fails against the buggy `max` version, where it counts 10 hours instead of 4, and passes with the fix.
- **Why the old tests missed it:** the existing stable-time test only ever set `stable_at`. With one timestamp, `min` and `max` give the same result.

I haven't committed anything. The fix still has to be deployed. After that, the affected cases (anything that reached `Stable` since 2025-09-02 18:15 UTC) need their costs recalculated and re-synced to the warehouse. The separate `get_hourly_rate` `TypeError`, which starts on 09-08, is still unfixed.

----- next turn -----

The TypeError is fixed in `get_hourly_rate`, and I added a test. All 36 tests in `tests/case_cost` and `tests/incident_cost` pass. Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `project.annual_employee_cost / project.business_year_hours`. Both columns on `Project` are nullable, so a project with either one set to NULL raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.
- The scheduler's cost job catches the error per case, so the job keeps going, but those cases never get a cost.
- The log shows the error from 2025-09-08 15:55, but not which project has the NULL. My guess is a project update that saved an explicit null, because the API schema allows `None` and `project.service.update` writes it straight to the column. That is unconfirmed. The project's rows should be checked.
- I did not find a code change that introduced this.

**Fix:** a missing `annual_employee_cost` or `business_year_hours` now falls back to the `Project` column default (50000 and 2080). The code reads the default from the column itself, so it stays in sync with the model. A `business_year_hours` of 0 also falls back, which avoids a divide-by-zero.

**Test:** `test_get_hourly_rate__missing_project_values_use_model_defaults` covers both values missing, only the cost missing and only the hours missing. It fails without the fix.

**Not changed:**
- `incident_cost/service.py` has the same `get_hourly_rate` and the same latent bug. I left it alone because you asked only about cases. It is a one-line copy of this fix if you want it.
- The NULL values are still in the project row. This fix makes the cost job tolerate them, but it doesn't stop the API from writing them.
- Cases that failed since 09-08 will get costs on the next hourly run after deploy.

----- next turn -----

## Recap

**What happened.** Since early September, case response costs in the finance warehouse were several times higher than before. For example, case 5363 went from $2,261 to $6,241 on 2025-09-09. Nobody had changed rates or cost models.

**Root cause.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in the function that finds when a participant's cost stops accruing. The timestamps are the case's `stable_at`, `escalated_at` and `closed_at`. The cut-off was supposed to be the earliest of them. With `max`, a case that has several of them keeps accruing cost up to the latest one.

**Deploy.** `main-65f7df6e` went out on 2025-09-02 at about 18:14–18:15 UTC and included `20f33137`. The previous image, `main-3e0445ff`, did not. The later deploy `main-51546e13` on 09-04 only carried the bug forward.

**Evidence.**
- There were no cost-spike warnings in `cost-sync.log` before the deploy.
- After it, five Stable cases were flagged with jumps of 147–265%.
- The first was case 5284 on 2025-09-03 at 11:20 UTC (3331 → 8804).
- Case 5356 on 09-06 also rose by about 390, roughly double its hourly norm, and was not flagged.
- Cost-sync 1.5.0, hourly rates and cost models are ruled out.

**Fix and test.** `min` is restored. The regression test `test_case_cost_stops_at_earliest_status_timestamp` fails on the buggy code and passes now.

**Second problem.** The hourly TypeError since 2025-09-08 came from a project whose `annual_employee_cost` or `business_year_hours` is NULL. `get_hourly_rate` divided `None` by an `int`, so those cases got no cost. It now falls back to the `Project` model defaults, with a test.

**Open items for the report.**
- The fixes are uncommitted and not yet deployed.
- Costs for cases that reached Stable since 2025-09-02 18:15 UTC need recalculating and re-syncing to the warehouse. The sync only flags jumps above about 100%, so smaller inflation went unflagged.
- I don't know which project has the NULL, or how it got there. A project update that saved an explicit null is my guess.
- `incident_cost/service.py` has the same unguarded division.
- The `FIRST_INFLATED` date is the first case flagged in the sync log. Smaller inflation earlier than that could exist but wasn't visible in the logs.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost