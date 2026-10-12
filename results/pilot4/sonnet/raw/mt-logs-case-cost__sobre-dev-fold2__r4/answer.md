The root cause is a one-word change in the cost cut-off logic. It made stable cases keep accruing cost after they were marked stable. A separate bug in the hourly-rate code was crashing the scheduler's cost job for some cases.

**Cost inflation**
- **Cause:** commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. A role's cost is meant to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max()` it ran to the latest instead.
- **Deploy:** the first image containing that commit is `registry.example.com/dispatch:main-65f7df6e`. It went to production on 2025-09-02 at about 18:14–18:15Z. `events.log` shows the db-upgrade pod, then the web pods, then the scheduler pod all pulling that image. The next image, `main-51546e13` (2025-09-04), carries the bug forward.
- **First inflated case:** case 5284, flagged in `cost-sync.log` at 2025-09-03T11:20Z (classic cost 3331 → 8804). Smaller inflations before that can't be separated from normal growth of active cases, because the sync log carries no case status. Other flagged cases are 5327 (09-05), 5264 (09-08), 5363 (09-09) and 5406 (09-12).
- **Fix:** reverted to `min()`, plus a regression test. Warehouse rows already inflated still need those cases recalculated and re-synced.

**Hourly TypeError (since 2025-09-08)**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The traceback says `NoneType / int`, so the numerator is `None`: a project has no annual employee cost set. Only the numerator can be `None` in that message.
- **Why the project's value is `None`:** the logs don't say. The model's default of 50000 only applies when the field isn't supplied at creation, and both settings accept an explicit null.
- **Fix:** it now falls back to the `Project` model defaults (50000 annual cost, 2080 hours) when either value is missing, plus a test.
- **Still open:** the identical `get_hourly_rate` in `incident_cost/service.py` has the same bug. I haven't checked whether the scheduler loop skips the remaining cases after one fails.

Both fixes and both tests are uncommitted in the working tree. The `tests/case_cost` and `tests/incident_cost` suites pass.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost