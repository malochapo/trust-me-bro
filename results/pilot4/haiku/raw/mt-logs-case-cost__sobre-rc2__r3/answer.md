## Incident recap

**Cost bug (inflated case response costs):** Commit `20f33137` (fix(case_cost): use the latest status timestamp as the cost cut-off) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for billed role time from the stable, escalated and closed timestamps. The code comment says "earliest", so `min` was the intended behaviour.

With `max`, the cut-off moves to the latest milestone. Escalated cases are no longer recomputed by the hourly job, so their cost froze at escalation. When such a case was later marked stable, the job recomputed it up to the stable time, billing all the time in between at once. Stable cases are then frozen, so the inflated figure stuck. Five cases were affected, with increases of 1.5x to 3.6x: 5284, 5327, 5264, 5363 and 5406, between Sept 3 and Sept 12.

**Deploy:** Commit `20f33137` is an ancestor of `65f7df6e`, which was deployed as image `main-65f7df6e` on Sept 2 at 18:14Z. The scheduler restarted on it at 18:15:30Z, and the first inflated sync was Sept 3 at 11:20Z.

**Fix:** `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` is back to `min`. A regression test covers the escalate-then-stable case. Already-inflated costs are not corrected; they need a targeted recalculation.

**Separate TypeError (hourly job failing for some cases since Sept 8):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without a null check. A NULL `annual_employee_cost` raised the error, and the job skipped those cases. The project API can save NULL, because project updates use `exclude_unset`. The fix falls back to the model defaults of 50,000 and 2,080. Tests cover it. The same unguarded division exists in `src/dispatch/incident_cost/service.py:133` and is not yet fixed.

**Open items:** the affected cases' costs need recalculation for the finance warehouse. I did not confirm which project or update set the NULL. The incident cost division should get the same fix.

Full test suite: 362 passed, 4 skipped, 8 failed. The 8 failures are in the ai, restricted case filter and entity tests, and they fail on the untouched code too.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost