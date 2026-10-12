## Recap

**Cost inflation**
- Commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`.
- A case that went stable and was later closed was therefore billed for its whole stable period. Case 5363 went from $2,261 to $6,241 when it was closed on Sep 9.
- It shipped in the `main-65f7df6e` deploy on 2025-09-02 at about 18:14Z. The first inflated case I can see is 5284 on 2025-09-03. It went from $3,331 to $8,804 at the 11:20Z sync. Other cost drops after the deploy look like normal fluctuation, and I found no earlier inflated case.
- Fix: the cut-off is back to `min()`. The regression test `test_case_cost_stops_at_earliest_status_time_when_closed_after_stable` fails on the old code and passes on the fix.
- Costs already stored for cases closed since Sep 2 are still inflated and need a backfill. The affected cases include 5284, 5327, 5264, 5363 and 5406.

**Hourly TypeError (from Sep 8)**
- `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. For some project the first value was `NULL`: the error says `NoneType / int`, so the numerator was `None`.
- Fix: any missing value now falls back to the Project model's default (50000 or 2080). The new test is `test_get_hourly_rate_falls_back_to_project_defaults`.
- The same unguarded division still exists in `src/dispatch/incident_cost/service.py:133`.
- The logs don't show which project it is, so that is still to be found.

All 21 tests in `tests/case_cost` pass. Nothing is committed yet.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost