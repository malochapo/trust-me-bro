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