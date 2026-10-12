## Recap

**What happened:** the finance warehouse's case costs were several times too high from early September. The cause was a one-line change in `20f33137` ("use the latest status timestamp as the cost cut-off"), which turned `min(timestamps)` into `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. Before the change, a case stopped accruing cost at the earliest of them. After it, a case that was escalated and later marked stable kept accruing until `stable_at` (or `closed_at`). Costs then jumped in the sync after the status change. Case 5363 went from $2,261 to $6,241 on 2025-09-09.

**Shipped by:** image `registry.example.com/dispatch:main-65f7df6e`, deployed on 2025-09-02. The db-upgrade pod pulled it at 18:14Z and the scheduler pod at 18:15Z. The previous deploy, `main-3e0445ff` on 08-27, did not contain the commit. The 09-04 deploy `main-51546e13` also contains it, but it is not the first to ship it.

**First inflated case:** case 5284, flagged `Stable`, went from 3331 to 8804 (+164%) in the 2025-09-03 11:20Z sync. It is the first in the logs after the deploy. A scan of the diffs between the deploy and that sync found no earlier jump of that kind. This is the first jump in the logs, not a recomputation of every case's cost.

**Fixed:** the cut-off is back to `min`, with a regression test (`test_case_cost_stops_at_earliest_status_timestamp`). Costs already in the warehouse for cases marked stable since 2025-09-02 are inflated. They should correct on the next hourly sync once the fix is deployed, assuming the sync overwrites changed rows. Finance may want to re-check any figures they've already reported.

**Second issue, separate:** from 2025-09-08 the hourly scheduler job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` 708 times. `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divided `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the logged errors show the annual cost was the missing value. Affected cases got no cost. It now falls back to the project model's defaults (50000 and 2080) for each missing value, with two tests added. I did not determine why it began on 09-08. `incident_cost/service.py` has the same division and is not fixed.

**Not committed:** both fixes and their tests are uncommitted in the working tree. `tests/case_cost` passes (22 tests); I did not run the full suite.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost