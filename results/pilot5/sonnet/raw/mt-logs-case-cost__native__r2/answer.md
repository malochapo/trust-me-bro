The cost bug is a one-word change in the case cost cut-off, and the hourly TypeError is a separate bug.

**Cost inflation**
- Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` for the cost cut-off in `get_participant_role_time_seconds`. A case's cost then ran on to its latest status timestamp instead of stopping at its first.
- That commit reached production in the `main-65f7df6e` rollout on 2025-09-02 at about 18:14Z.
- The first inflated case I can see in the logs is 5284 on 2025-09-03 at 11:20Z. Its classic cost went from 3331 to 8804, and `case-cost-sync` flagged it.
- The cost-sync diffs between the rollout and that sync show no unusual jumps, but a smaller inflation could be hidden in normal hourly noise. If you need an exact first-inflated case, check the `stable_at`, `escalated_at` and `closed_at` timestamps in the database.
- The fix, a revert to `min` plus a regression test, is in the working tree, uncommitted.
- Costs synced to the warehouse since 2025-09-02 need recomputing.

**Hourly TypeError**
- `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. A project saved with a NULL cost setting made the scheduler's hourly case cost job raise `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.
- The `fraud` project appears in the scheduler log around 2025-09-08 14:54, and the first error is at 15:55. I believe `fraud` is the project with the NULL setting, but the log doesn't name it.
- The error text shows the numerator was `None`, so `annual_employee_cost` is the missing setting. If `business_year_hours` was also NULL, the message would be the same, so I can't rule that out.
- The fix falls back to the Project model defaults (50000 and 2080), with tests. It's in the working tree, uncommitted.
- `incident_cost/service.py` has the same unguarded division and is unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost