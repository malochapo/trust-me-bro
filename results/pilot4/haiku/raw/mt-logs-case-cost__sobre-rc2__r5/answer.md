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