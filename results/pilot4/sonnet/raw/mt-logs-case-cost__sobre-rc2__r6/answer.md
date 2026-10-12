**Recap**

- **Cost inflation:** `20f33137` changed `min(timestamps)` to `max(timestamps)` in the cost cut-off. Cost then ran to the latest of `stable_at`, `escalated_at` and `closed_at`. It reached production in `main-65f7df6e`, deployed 2025-09-02 at 18:14Z (the scheduler was replaced by 18:15Z). The first inflated cost I can see is case 5284 on 2025-09-03: classic 3331 → 8804 (+164%) at 11:20Z, flagged by finance's job. Other large jumps between the deploy and that sync were small new cases accruing normally. Smaller inflations may exist that the sync's flagging threshold missed, so that date is the first one visible in the logs.
- **Fix:** the cut-off is back to `min`, with a regression test. Costs already stored for cases that went stable or closed since 2025-09-02 18:15Z still need recalculating, and finance should re-sync afterward.
- **TypeError:** it started 2025-09-08 (708 occurrences) in `get_hourly_rate`. Every one reads `unsupported operand type(s) for /: 'NoneType' and 'int'`. The `None` is on the left of the division, so it is `annual_employee_cost`. `business_year_hours` was an int in all of them. The fix falls back to the model defaults (50000 and 2080) when either is missing, with tests. I don't know what cleared the setting, or which projects are affected.
- **Open items:** the identical `get_hourly_rate` in `incident_cost/service.py` is unfixed. Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost