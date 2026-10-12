## Recap

**Inflated costs.** Since the deploy of 2025-09-02, the finance warehouse has been receiving case response costs that are several times too high. Commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds()` from `min(timestamps)` to `max(timestamps)`. The cut-off should be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that was escalated and later marked stable or closed kept accruing cost until the latest of those times.

- Case 5363 is the example. Its cost froze at $2,261 on Sep 5. When it was marked stable on Sep 9, the cut-off moved forward about 92 hours, which added about $3,980 and gave $6,241.
- The log shows the same pattern for other cases that went stable or closed. A scan of `cost-sync.log` for jumps over $400 found five, all in Stable status:

| Case | First flagged | Change |
|---|---|---|
| 5284 | Sep 3 | $3,331 → $8,804 |
| 5327 | Sep 5 | $2,244 → $5,539 |
| 5264 | Sep 8 | $3,285 → $11,987 |
| 5363 | Sep 9 | $2,261 → $6,241 |
| 5406 | Sep 12 | $1,975 → $4,945 |

- The first jump was on Sep 3, the day after the deploy, and there were none before the deploy. The Sep 3 date comes from the first jump over $400 in the sync log. A smaller inflation earlier than that couldn't be ruled out from the logs.
- I restored `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. It fails on the old code.

**Deploy.** The fix was merged on 2025-09-02 and first reached production as `dispatch:main-65f7df6e` at about 18:14Z that day. The earlier deploy, `main-3e0445ff`, doesn't contain it. The later deploy, `main-51546e13` on Sep 4, also does.

**Hourly TypeError.** From Sep 8, the scheduler's case cost job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` for a few cases every hour.
- `get_hourly_rate()` divides `project.annual_employee_cost` by `project.business_year_hours`, and a project had a NULL there.
- It now uses the `Project` model defaults (50000 and 2080) for whichever value is missing.
- I added `test_get_hourly_rate__missing_values_use_project_defaults`, which fails on the old code.
- The logs don't show which project it was. `incident_cost/service.py` has the same bug, which I left alone.

**Still to do.**
- Nothing is committed or deployed yet, so the fixes aren't in production.
- Finance needs to recompute the warehouse rows for cases that were stable, escalated or closed since Sep 2.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost