## Recap

**Cost inflation (the first bug):** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For cases past New/Triage, the billing cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` rather than the earliest. A Stable case whose later timestamp came after the first stop kept accruing participant time. The first inflated case was 5284 on 3 Sep. Case 5363 (2,261 → 6,241 on 9 Sep) is the example from the report. The code now uses `min` again, and a regression test covers the case that failed before.

**Deploy:** `dispatch-web` rolled out `registry.example.com/dispatch:main-65f7df6e` on 2 Sep 2025 at 18:14Z. That image contains `20f33137`. The scheduler was redeployed with the same image at 18:15Z.

**Hourly TypeError (the second bug):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no NULL check. A NULL `annual_employee_cost` raised the TypeError, and the scheduler dropped that case's cost for the hour. The first occurrence was 8 Sep 15:55. The fix falls back to the `Project` model's column defaults (50000 and 2080) for either missing value. Both new tests failed before the fix.

**Open:**
- The 5363 timestamps have not been checked against the database.
- Why the project values became NULL is unknown. The logs have no project-level event, and no commit in the window touches them.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division and is not fixed.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```