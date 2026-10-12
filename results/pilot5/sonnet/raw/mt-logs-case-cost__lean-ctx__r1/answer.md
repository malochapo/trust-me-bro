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