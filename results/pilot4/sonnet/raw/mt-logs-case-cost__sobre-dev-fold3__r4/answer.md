## Recap

**The cost bug.** Commit `20f33137` (2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. The cost cut-off for a case is the earliest of `stable_at`, `escalated_at` and `closed_at`. After the change, a later escalation or close moved the cut-off forward and added the idle time after the case went stable. Costs jumped when that later timestamp was set, as with case 5363 ($2,261 to $6,241 on 2025-09-09).

**The deploy.** Image `main-65f7df6e` rolled out on 2025-09-02 at about 18:14Z (db-upgrade, then web, then scheduler). It was the first build containing `20f33137`. The earlier `main-3e0445ff` build predates the commit. `main-51546e13` (2025-09-04) came after the first inflated cost.

**First inflated cost.** I scanned every cost increase in cost-sync.log. Only five are large: 2025-09-03, 09-05, 09-08, 09-09 and 09-12. The first is case 5284 on 2025-09-03, 3331 to 8804. Nothing before the deploy looks like it, so smaller inflated costs earlier on 2025-09-02 or 2025-09-03 are unlikely, though I can't fully rule them out from cost deltas alone.

**The TypeError.** Since 2025-09-08 the hourly scheduler job hit `None / int` in `get_hourly_rate()`. A project had no `annual_employee_cost`, the left operand. In my first recap I wrongly blamed `business_year_hours`. I don't know why it started on 09-08, because the logs don't show a project edit.

**Changes made.** Neither is committed:
- Restored `min()` in `get_participant_role_time_seconds()`. The new test `test_case_cost_stops_at_earliest_status_timestamp` fails on the old code and passes with the fix.
- `get_hourly_rate()` now falls back to the project model defaults (50000 and 2080) for a missing value. The new test `test_get_hourly_rate__missing_values_use_project_defaults` covers it. I didn't confirm this one fails on the old code.

**Still to do:**
- Deploy both fixes.
- Recalculate costs inflated since 2025-09-02 and correct the warehouse rows.
- Check which project has the NULL `annual_employee_cost`.
- Apply the same None fallback to `incident_cost`, which has the same flaw.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost