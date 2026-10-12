**Root cause:** commit `20f33137` (Jordan Lee, Sept 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. That makes a case's cost cut-off the latest of its stable, escalated and closed timestamps, not the earliest. Once a case is stable, participants should stop accruing time; with `max`, a later timestamp (a stable mark set after escalation, or a later close) pushes the cut-off forward and keeps costs growing.

**Shipped by:** the Dispatch image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14–18:15 UTC** (`events.log`, ReplicaSet `dispatch-web-zrhzjwmzrh`). `20f33137` is an ancestor of `65f7df6e`, and the previous image `main-3e0445ff` predates it, so this is the first production build with the change.

**Evidence:**
- The first flagged jump is case 5284 on **Sept 3 11:20** (3331 → 8804), the first hourly sync after that rollout. Nothing was flagged before Sept 2.
- Case 5363 (the one you named) was first synced at 131 on Sept 4, then grew about 146 per hour while open. Its cost was flat from Sept 5 16:20 (2261) until Sept 9 12:20, when it jumped to 6241 in the hour it was marked stable. A cut-off that moves forward to the latest timestamp fits that jump.
- Later flags on the same pattern: 5327 (Sept 5), 5264 (Sept 8), 5406 (Sept 12).

**Why tests didn't catch it:** `tests/case_cost/test_case_cost_service.py` only sets `stable_at`, so `min` and `max` return the same value. No test covers a case with a later `closed_at` or `escalated_at`.

**Caveats:**
- I couldn't see the case's `escalated_at` or `closed_at` values; the data only has the sync output. The mechanism is inferred from the code and the timing, not confirmed against the database.
- The commit title ("latest status timestamp") and the code comment ("Determine the earliest relevant timestamp") disagree. I don't know why Jordan wanted `max`, so the author should confirm what problem it was meant to solve before reverting.

**Side finding:** the scheduler logged 708 errors of the form `unsupported operand type(s) for /: 'NoneType' and 'int'` in `get_hourly_rate` (`case_cost/service.py:118`). That's `project.business_year_hours` being `None` in the new cost model. It's separate from the classic-cost jump but worth a look.

**Next steps (no code changed):**
1. Revert the one line to `min(timestamps)` and add a test with a stable case whose `closed_at` is later than `stable_at`.
2. Recalculate affected cases' costs and resync them to the finance warehouse, since the hourly sync overwrites warehouse rows from the Dispatch API.

----- next turn -----

The fix is in and the regression test is in place. The test fails on the old `max` code (`7200.0 == 3600`) and passes on the fix.

**Changes**
- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`, so the cut-off is the earliest of stable, escalated and closed again. This matches the function's own comment.
- `tests/case_cost/test_case_cost_service.py`: new `test_case_cost_stops_at_first_cutoff_timestamp`. It sets a participant assumed 2 hours ago, `stable_at` 1 hour ago and `closed_at` now, and expects 3600 seconds. The existing stable test didn't catch the bug because it only sets `stable_at`.

**Verification**
- `python -m pytest tests/case_cost -q` (PostgreSQL running locally): 20 passed.
- I reintroduced `max` temporarily to confirm the new test fails, then restored `min`.
- I didn't run the full test suite, only `tests/case_cost`.

**Not done**
- Nothing is committed or deployed.
- Affected cases still hold inflated costs in Dispatch and in the finance warehouse. Those need recalculating and a resync once this ships. I haven't touched production or the warehouse.
- The commit title said "latest status timestamp" while the code comment said "earliest". I went with the comment and the stop-at-stable behaviour the existing tests assert. Jordan Lee wrote the original change, so confirm with them that no case they were fixing depended on `max`.

----- next turn -----

The hourly case-cost job's TypeError is fixed, and the cases with missing project settings now get a cost. All 23 case-cost tests pass against PostgreSQL.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no `None` check. Some projects have NULL in one or both columns. Their defaults (50000 and 2080) only apply when a row is inserted, so an existing row with NULL keeps `None`. The first error is at 2025-09-08 15:55, and the count rises from 9 that day to 146–153 per day by Sept 13–14. I didn't find a commit or log entry that changed the project rows on Sept 8, so I can't say what nulled them.

**Fix:**
- A missing `annual_employee_cost` or `business_year_hours` now falls back to the project model's column default, read from `Project.__table__` so it can't drift from the model. The fallback values are 50000 and 2080.
- `get_hourly_rate` now uses that fallback.
- `from dispatch.project.models import Project` is added to the service's imports. It's safe, since `case_cost/models.py` already imports from that module.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_for_missing_values`, parametrized over a missing cost, a missing hours value, and both missing.
- I also added `import pytest` at the top of the file, which the new test needs.
- Against the original code, all three cases fail with the same TypeError as in the logs. With the fix they pass.

**Not changed, but you should know:**
- `src/dispatch/incident_cost/service.py:131` has the same unguarded division. The scheduler log has an incident-cost task error too, so that job probably has the same problem. I left it alone because you asked for the case job. It's a one-function change if you want it.
- A project with `business_year_hours = 0` would still fail, with a ZeroDivisionError. The fallback only covers `None`.
- Nothing is committed. The affected projects need checking: their NULL values are still in the database, so their costs are only right while the fallback applies.

----- next turn -----

## Recap

**Incident: inflated case response costs (finance warehouse)**

**Root cause:** `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` used `max()` instead of `min()` when choosing the cost cut-off from the stable, escalated and closed timestamps. The function's own comment said "earliest", and the cut-off should be the earliest. With `max`, a case that was closed or escalated after it was stable kept accruing participant time after stable. Case 5363 was flat at 2261 until it was marked stable on Sept 9, then jumped to 6241.

**Deploy:** commit `20f33137` (Jordan Lee, Sept 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") was built into image `main-65f7df6e` and rolled out to `dispatch-web` and `dispatch-scheduler` at 18:14–18:15 UTC on Sept 2. The first inflated cost in the sync was case 5284 on Sept 3 at 11:20 (3331 → 8804).

**Separate issue:** from Sept 8, the scheduler's hourly case-cost job logged a TypeError for some cases. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. The project's values were NULL, and the model defaults only apply on insert. I did not find what nulled those values on Sept 8.

**Changes (not committed or deployed):**
- `case_cost/service.py`: reverted the cut-off to `min(timestamps)`.
- `case_cost/service.py`: `get_hourly_rate` falls back to the project model's column defaults for a missing `annual_employee_cost` or `business_year_hours`. The defaults are read from `Project.__table__`, so they stay in sync with the model.
- `tests/case_cost/test_case_cost_service.py`: added `test_case_cost_stops_at_first_cutoff_timestamp` (fails on `max`: `7200.0 == 3600`) and `test_get_hourly_rate_uses_project_defaults_for_missing_values` (fails on the original code with the TypeError).
- `python -m pytest tests/case_cost`: 23 passed against the local PostgreSQL.

**Open items:**
- Costs already inflated in Dispatch and the finance warehouse need recalculating and a resync after the fix ships.
- The projects with NULL settings still need an owner to set real values.
- `incident_cost/service.py:131` has the same unguarded division. The scheduler log also shows an incident-cost task error. I did not change it.
- `business_year_hours = 0` would still raise a ZeroDivisionError. The fallback only covers `None`.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```