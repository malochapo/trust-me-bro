## Recap

**Bug 1: inflated case costs.** `get_participant_role_time_seconds` picked the maximum of the stable, escalated and closed timestamps as the cut-off for participant time, instead of the minimum. When a case was escalated and later marked Stable, every participant was charged for the gap between the two. Commit `20f33137` (Sept 2, 2025) made that change. It shipped in `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC. The first inflated cost in the logs is case 5284, which jumped from 3331 to 8804 in the sync at 2025-09-03 11:20 UTC. Five cases were flagged after Stable transitions: 5284, 5327, 5264, 5363 and 5406. Fixed by reverting to `min()`, with a regression test. The affected cases still need recalculation in the warehouse, because the hourly job only upserts rows whose values change.

**Bug 2: hourly TypeError.** `get_hourly_rate` divided a NULL `annual_employee_cost` by `business_year_hours`. The scheduler logged 708 such errors, starting 2025-09-08 15:55, and skipped those cases. Fixed by falling back to the `Project` model's column defaults (50000 and 2080) when either value is NULL, with two regression tests. I did not establish why those project values became NULL around Sept 8.

**Verification:** the new tests fail on the old code. The full suite shows 362 passed and 8 failed, and the same 8 tests fail on clean HEAD (AI service, restricted case filter, entity service). All changes are uncommitted.

**Open items:** `incident_cost/service.py:133` has the same unguarded division, so incident costs for projects with NULL values will hit the same error. Not fixed; say if you want it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost