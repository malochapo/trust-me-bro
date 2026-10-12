**Root cause:** commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from `min` to `max`. For a case that has been escalated and later marked stable, the cut-off moves from the escalation time to the stable time, so every participant role is billed for the extra interval. The cost is then frozen at the new, higher value.

**The deploy:** `dispatch:main-65f7df6e` rolled out on 2025-09-02 at 18:14Z (11:14 PDT). `65f7df6e` contains `20f33137`, and no other deploy landed between them. `dispatch-web` and `dispatch-scheduler` both moved to that image that afternoon. The first flagged jump came the next day, 2025-09-03 11:20Z, for case 5284.

**The evidence:**

- **The change.** In `src/dispatch/case_cost/service.py`, `20f33137` changed line 353 from `participant_role_renounced_at = min(timestamps)` to `max(timestamps)`. The commit title says "use the latest status timestamp", but the code comment just above it says "Determine the earliest relevant timestamp for cost calculation cut-off", and the docstring says the role time is used "if it happened before the case was marked as stable or closed". The `min` came in with the Stable status work (`200cd428`, June 2025). Current `main` (`51546e13`) still has `max`.
- **The jumps line up with the change.** cost-sync raised its first stable-case warnings on 2025-09-03 (case 5284, $3,331 → $8,804) and 2025-09-09 (case 5363, $2,261 → $6,241). Before that deploy there were no such warnings. Case 5406 followed on 2025-09-12 ($1,975 → $4,945). These jumps happen exactly when a case becomes Stable, which is when `max` moves the cut-off to `stable_at`.
- **Caveat.** Hourly diffs in cost-sync show large swings every day from 2025-08-25 onward, so the daily totals alone don't prove the regression. The stable-transition warnings are the clear signal.

**Side finding (not the inflation):** `scheduler.log` shows `unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate` (`case_cost/service.py:118`), which divides by `project.business_year_hours`. These errors start 2025-09-08 and continue through 2025-09-14, and they abort cost updates for those cases. That likely leaves some case costs stale, so it's worth a separate look. I haven't confirmed which projects have a null `business_year_hours`.

I didn't change any code.

----- next turn -----

The fix is in and the regression test catches the bug. Nothing is committed.

**The fix:** in `src/dispatch/case_cost/service.py`, the cut-off is back to `min(timestamps)`. The code comment and docstring already describe the earliest of stable/escalated/closed, so I reverted `20f33137`'s one-line change. Its title says "use the latest status timestamp", which I can't reconcile with the surrounding code. If someone had a real case that needed the later timestamp, that would need a different fix, so it's worth a check with Jordan Lee.

**The regression test:** `test_case_cost_stops_at_earliest_stable_or_escalated_time` in `tests/case_cost/test_case_cost_service.py`. It sets up an assignee active for two hours, escalated 90 minutes ago, then marked stable an hour ago. The role time should stop at escalation (1800s). On the buggy code it returned 3600s and failed. It passes with the fix.

**Test results:**
- `tests/case_cost`: 20 passed.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). The same 8 fail on the unmodified code, so they predate this change. I didn't investigate them.

**Not fixed:** the `NoneType / int` errors in `get_hourly_rate` (`business_year_hours` is null for some projects) are still there. That's a separate bug from the inflation.

----- next turn -----

The hourly job now costs cases whose project is missing the annual employee cost or the business year hours. It falls back to the project model's defaults (50000 and 2080). Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no null check. Both columns are nullable, and the `ProjectUpdate` schema accepts `null`. A project with a null cost raises `TypeError`. The traceback's numerator is `annual_employee_cost`, so that is the field that was null on the affected projects. The logs don't record project names, so I can't say which projects they are or what cleared the value. The `TypeError` count rises from 9 on Sep 8 to 146 on Sep 14.

**Effect:** the exception is raised in the new-model calculation, before the classic model runs. So a case on such a project gets no cost update at all for that run, not just a missing new-model value.

**Fix:** `get_hourly_rate` now replaces a `None` cost or hours value with the column default taken from `Project.__table__`, so the defaults stay in one place. `Project` is imported from `dispatch.project.models`.

**Tests added** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers a null cost, null hours, and both null.
- `test_update_case_response_cost_with_missing_project_cost` runs the full update on a project with both values null and checks that the classic cost is positive.

Both failed with the production `TypeError` before the fix and pass after it. All 22 case cost tests pass. The full suite has the same 8 failures as before my changes (in `tests/ai`, `tests/database` and `tests/entity`), which fail on the unmodified code too.

**Left alone:** `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` without the fallback. The incident cost job would hit the same error for a project with a null value. I didn't change it since you asked about the case cost job. The same fix would apply there if you want it.

----- next turn -----

Here is the recap for the incident report. The fix is in the working tree and not committed.

**What happened**

- **Cost bug:** on 2025-09-02, commit `20f33137` changed the cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. For a case that was escalated and later marked stable, participant role time ran until the stable time, not the escalation time. Cost also froze at the higher value. Case 5284 went from $3,331 to $8,804 in the Sep 3 sync, and case 5363 went from $2,261 to $6,241 on Sep 9.
- **Deploy:** `dispatch:main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14Z. `65f7df6e` includes `20f33137`, and no other deploy landed between them.
- **Fix:** `min` is restored in `src/dispatch/case_cost/service.py`. A regression test covers the escalated-then-stable case and fails on the buggy code.
- **Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no null check. A project with a null `annual_employee_cost` raised `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. That aborted the whole case's cost update, including the classic model. Errors began 2025-09-08. The fix falls back to the model defaults (50000 and 2080), with tests. The incident cost service has the same unguarded division and is not fixed.
- **Open items:** the trigger that nulled the project setting is not found in the logs, and I haven't identified which projects are affected. The same unguarded division in the incident cost service has not been fixed.

**Report lines**

```text
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```

`FIRST_INFLATED` is the first inflated cost in the logs. Cost-sync runs hourly, and the Sep 2 18:20 run through the Sep 3 10:20 run show no flagged jump. Case 5284's jump is the first one after the deploy that the logs identify.