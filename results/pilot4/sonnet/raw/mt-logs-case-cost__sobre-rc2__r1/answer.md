## Recap

**Cost inflation**
- Since early September, the finance warehouse showed case response costs several times higher than before for cases marked stable. One example is `dispatch-default-security-5363`, which went from $2,261 to $6,241 on 2025-09-09.
- Commit `20f33137` ("use the latest status timestamp as the cost cut-off", 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. That moved the cost cut-off for a stable case from `stable_at` to the latest of `stable_at`, `escalated_at` and `closed_at`, or to now if only `stable_at` is set. Participants on stable cases kept accruing cost.
- The first production image containing the commit was `dispatch:main-65f7df6e`, rolled out around 18:14–18:16 UTC on 2025-09-02. The next image, `main-51546e13`, also contains it but did not introduce it.
- The first flagged inflation is case 5284 on 2025-09-03 at 11:20Z (3331 → 8804, +164%). The earlier hourly diffs after the deploy look like normal growth on active cases.
- I reverted to `min(timestamps)` and added `test_case_cost_stops_at_earliest_status_timestamp`. It failed before the fix and passes after.

**Hourly TypeError (separate issue)**
- Since 2025-09-08, `get_hourly_rate()` raised `unsupported operand type(s) for /: 'NoneType' and 'int'` for cases in a project with a NULL setting. The scheduler caught the error per case, so only that project's cases lost their cost update.
- The error message names `NoneType` as the dividend, so the missing value is `annual_employee_cost`. A missing `business_year_hours` would have produced an `int` and `NoneType` message.
- The fix falls back to the project model defaults (50000 and 2080) when either value is missing. The test is `test_get_hourly_rate__project_settings_unset`.

**Open items**
- Nothing is committed yet.
- Stable cases need recalculating once the fix is deployed, and the warehouse needs re-syncing for cases marked stable since 2025-09-02.
- `incident_cost/service.py:133` has the same unguarded division.
- I could not tell from the logs why the project's value became NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost