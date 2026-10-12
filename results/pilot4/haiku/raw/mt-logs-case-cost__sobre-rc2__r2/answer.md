**Recap**

- **Cost inflation:** Commit `20f33137` (Sep 2) changed the cut-off in `get_participant_role_time_seconds` from the earliest milestone (escalated, stable or closed) to the latest. Time between escalation and stable/closed was then billed at once when the later milestone was recorded. Case 5284 jumped from 3331 to 8804 on Sep 3, the first clear case. Case 5363 jumped from 2261 to 6241 when it was marked stable on Sep 9.
- **Deploy:** Image `main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on Sep 2 at 18:14–18:15 UTC. The scheduler runs the hourly cost job, so it's where the bug took effect. The scheduler was on that image until Sep 4.
- **Fix:** Reverted the cut-off to `min(timestamps)`, matching the code comment. Added `test_get_participant_role_time_seconds_stops_at_first_milestone`, which fails on the old code (7200 vs 3600 s) and passes on the fix.
- **TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with NULL `annual_employee_cost` raised on every hourly run from Sep 8. The fix falls back to the model defaults (50,000 and 2,080) and adds `test_get_hourly_rate_falls_back_to_project_defaults`. How those projects got NULL is not in the logs; an explicit null through the project update path is the likely route.
- **Tests:** 361 passed, 4 skipped, 8 failed. The 8 failures are in the AI, database and entity tests and also fail on the untouched tree.
- **Not done:**
  - Nothing is committed.
  - The `incident_cost` module has the same `get_hourly_rate` bug, which I haven't fixed.
  - Warehouse rows already inflated or skipped need recalculating.
  - `FIRST_INFLATED` is the first clearly inflated case I could find. The Sep 2 deltas were at most 230, roughly twice the typical hourly rate of 97, so I can't rule out a smaller inflation that day.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```