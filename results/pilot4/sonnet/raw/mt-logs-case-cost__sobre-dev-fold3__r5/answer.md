## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function sets the point where a case stops accruing cost, taken from `stable_at`, `escalated_at` and `closed_at`. With `max()`, a case with a later timestamp than `stable_at` kept accruing cost after it went Stable.
- **Deploy:** the first image containing the commit was `main-65f7df6e`, rolled out Sep 2 at about 18:14Z. The Sep 4 deploy (`main-51546e13`) still carried the bug.
- **Evidence:** the first jump in `cost-sync.log` is case 5284 on Sep 3 at 11:20Z ($3,331 → $8,804). Four more Stable cases jumped on later days. There were no such jumps before the deploy. I saw no sign that the finance job's Sep 1 upgrade (1.4.2 → 1.5.0) or a rollback was involved.
- **Date caveat:** "first inflated" is the first jump I could see in the logs, an hourly increase above $400. Smaller inflations earlier that day would not stand out, and I didn't check for them.
- **Fix:** reverted to `min()`, with a regression test for a stable case that also has later `escalated_at` and `closed_at`. Without the fix, that test fails.
- **Still open:**
  - The fix has to be deployed.
  - Warehouse rows for cases that went Stable since Sep 3 need recomputing.
  - The mechanism is inferred, because the logs don't show those timestamps for the affected cases.

**Hourly TypeError**
- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`, and a project had `annual_employee_cost` NULL. The columns are nullable, and the model default only applies on insert. There were 708 tracebacks, the first at 2025-09-08 15:55. Only that project's cases failed, and they also lost their classic cost update.
- **Fix:** a missing value now falls back to the `Project` model default (50000 and 2080), with tests.
- **Not done:** `incident_cost/service.py` has the same weakness. I haven't touched it. I couldn't tell from the logs which project it is or why it started Sep 8.

Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost