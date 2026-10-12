**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). That function decides when each participant's time stops accruing. The original `min` stopped accrual at the earliest of stable, escalated and closed. `max` stops it at the latest, so time between an earlier escalation and a later stable mark gets billed.

**Shipped by:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out 2025-09-02 at 18:14–18:15 UTC (`events.log`, `dispatch-web` and `dispatch-scheduler`). Commit `65f7df6e` contains `20f33137`, and `3e0445ff`, the previous image, does not. The scheduler runs `calculate_cases_response_cost` hourly, so it picked up the change on that deploy.

**Why the timing fits:**
- The first cost jump in `cost-sync.log` is 09-03 11:20 (case 5284), the first one after that deploy. Five stable cases jumped between 09-03 and 09-12, each flagged by the sync as "+150% to +265%".
- The later deploy `main-51546e13` (09-04) doesn't touch case cost. The cost-sync 1.5.0 rollout on 09-01 is before the 09-02 deploy and doesn't line up with the jumps.
- Case 5363 accrued about 145 per hour while open, then stopped changing at 09-05 16:20 (consistent with an escalation freezing it under either version). On 09-09 12:20 it jumped to 6241 when it was marked stable. Under `max` that moved the cut-off forward to the stable time, so the escalated period was billed too.

**Not verified:** the logs don't record status timestamps per case, so the escalation for 5363 is inferred from the freeze pattern. To confirm, check `status`, `escalated_at`, `stable_at` and `closed_at` for case 5363 in the Dispatch DB. The existing test `test_case_cost_stops_at_stable_time` only has one cut-off timestamp, so the test suite didn't catch this.

**Separate problem:** from 09-08, `scheduler.log` has 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` tracebacks at `get_hourly_rate` (`service.py:118`). These come from a project where `annual_employee_cost` is None. The loop in `scheduled.py` catches each one and skips that case, so those costs go stale rather than inflated. The logs don't say which project, so it's worth a separate look.

I haven't changed any code. For the fix, the likely move is reverting to `min` (or otherwise capping at the first escalation/stable/closed time), then recomputing affected stable cases, since the warehouse already holds the inflated values.

----- next turn -----

The fix is in, with a regression test that fails on the old code and passes on the fix. I haven't committed anything.

**The fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. The cut-off is now the first of escalated, stable or closed, which is what the function's own comment says it should be.

**The regression test:** `test_case_cost_stops_at_first_status_change` in `tests/case_cost/test_case_cost_service.py`. A participant is active for 3 hours, the case escalates 2 hours ago and is marked stable 1 hour ago. The test expects 3600 seconds (cost stops at escalation). On the broken code it fails with `assert 7200.0 == 3600`, which is the over-billing from the incident.

**Test results:**
- `python -m pytest tests/case_cost/`: 20 passed, including the new test.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). I stashed my two edits and ran those files on the original code, and the same 8 fail there, so they predate this change and are unrelated to case cost. I didn't investigate them.

**Still open:**
- The warehouse still holds the inflated values for the affected stable cases (5264, 5284, 5327, 5363, 5406, and any others). The scheduler won't recompute stable cases whose cost was updated after `stable_at`, so those need a manual recalculation or a backfill. I haven't done that.
- The separate `TypeError` from `get_hourly_rate` when `annual_employee_cost` is None is still there. I didn't change it, since it's a data problem rather than a code one. It's worth finding which project has the null value.

----- next turn -----

The TypeError comes from projects with a null `annual_employee_cost` or `business_year_hours`. Those cases now get a cost, using the model defaults for whichever value is missing. The full suite is at 362 passed, with the same 8 unrelated failures as before. I haven't committed anything.

**Cause:** `get_hourly_rate` (`src/dispatch/case_cost/service.py`) divides `annual_employee_cost` by `business_year_hours`. Both columns are nullable, and the Project schema has allowed an explicit `None` since commit `2d732e5d` (May 2025), so a project saved with either field cleared produces `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler catches that per case and skips the case, so its cost goes stale rather than wrong. The logs don't name the projects, and I can't tell from them what changed on 09-08. To find the affected projects, run `SELECT name, annual_employee_cost, business_year_hours FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL;`.

**Changes:**
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now module constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and the schema defaults both use them, so they can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default only when its value is `None`. A real `0` is kept, so it's still caught by the division rather than silently replaced.
- `tests/case_cost/test_case_cost_service.py`: two new tests. One covers the rate fallback for both missing values and for each one separately. The other checks that `calculate_case_response_cost` returns integer costs for a project with both values missing. I ran them first and they failed with the same `TypeError`.

**Not changed:** `src/dispatch/incident_cost/service.py:133` has the same `get_hourly_rate` code, so incident costs for those projects would hit the same error. The logs show no such TypeError from the incident job, so I left it alone. Say if you want it fixed the same way.

----- next turn -----

Here's the recap for the incident report. The six lines at the end are the fields you asked for.

**Summary**

- **What happened:** Starting with the 09-02 deploy, stable cases had their response cost inflated, sometimes several times over. For example, case 5363 went from 2261 to 6241 on 09-09, and case 5264 went from 3285 to 11987 on 09-08. The cause was commit `20f33137`, which changed the cost cut-off from `min` to `max` over the stable, escalated and closed timestamps. Accrual then ran past the first status change and was billed up to the latest one. The function's own comment said "earliest relevant timestamp", so `min` was the intended behaviour.
- **Fix:** `src/dispatch/case_cost/service.py` now uses `min` again. A regression test, `test_case_cost_stops_at_first_status_change`, reproduces the over-billing (7200 s instead of 3600 s) and passes with the fix.
- **Second issue:** Since 09-08, the hourly job also logged a `TypeError` for some cases. The cause is a null `annual_employee_cost` or `business_year_hours` on the project. The job skipped those cases, so their costs went stale. `get_hourly_rate` now uses the model defaults (50000 and 2080) for whichever value is missing. Tests cover this.
- **Test results:** `python -m pytest` gives 362 passed, 4 skipped, and 8 failed. The 8 failures are in the AI, database and entity tests, and they fail on the original code too.

**Open items**

- The warehouse still has inflated values for the affected stable cases, so they need a recalculation.
- The incident-cost module has the same `get_hourly_rate` code and would hit the same `TypeError` for those projects. The logs show no such error from the incident job, so I haven't changed it.
- I haven't checked which projects have null settings, and I haven't confirmed the escalation timeline for 5363 against the database.
- Nothing is committed.
- The first inflated date is based on the diffs: 09-02 19:20 shows a normal-sized increase, and 09-03 11:20 (case 5284, 3331 → 8804) is the first clearly inflated value.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost