## Recap

**Cost bug.** In `get_participant_role_time_seconds`, commit `20f33137` changed the cost cut-off from `min` to `max` of the stable, escalated and closed timestamps. A case that was escalated and then marked stable kept accruing participant time until the stable time, although the escalated-case recalculation had frozen its cost at escalation. Case 5363 went from $2,261 to $6,241 that way. The fix restores `min`, and `test_case_cost_stops_at_first_status_change_after_escalation` covers it. The test fails on the old code and passes on the fix.

**Deploy.** The `main-65f7df6e` image (commit `65f7df6e`) was rolled out to `dispatch-web` between 2025-09-02 18:14 and 18:15 UTC. The first commit that contains `20f33137` is in that build. The earlier `main-3e0445ff` build does not contain it.

**First inflated case.** The first flagged inflated cost is case 5284, on 2025-09-03. The flags only cover cases over the warning threshold, so an earlier inflated case that wasn't flagged would not show up in these logs.

**Hourly TypeError.** It occurs when a project's `annual_employee_cost` is NULL. The traceback's left operand is `NoneType`. Each affected case is logged and skipped, so it gets no cost. `get_hourly_rate` now falls back to the project model defaults (50000 and 2080), and there are three new tests for it. Two of them failed on the old code. The `incident_cost` service has the same code and is not fixed. Eight unrelated tests fail on clean HEAD too, six of them because the test environment has no network access.

**Not done.** Nothing is committed. The cases whose costs were inflated still need recalculation in the warehouse, and the incident-cost helper needs the same NULL handling.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost