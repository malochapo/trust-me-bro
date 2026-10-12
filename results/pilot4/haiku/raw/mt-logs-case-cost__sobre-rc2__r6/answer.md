Here is the recap for the incident report. The first inflated case is the earliest large jump in the logs after the Sep 2 deploy. The earlier 5284 cost jump on Sep 3 is the only one of that size between Sep 2 and Sep 4.

**Summary**

- **What happened:** Since early September, classic case response costs for cases that went Stable were inflated, for example case 5363 went from $2,261 to $6,241 when it was marked stable on Sep 9. The cause was commit `20f33137`, which changed the cost cut-off from the earliest status timestamp to the latest. A case that was escalated and then marked stable kept accruing participant time until the stable time, so its cost was overstated. Five cases were flagged by the sync check (5284, 5327, 5264, 5363, 5406); each jump happened at the Stable transition.
- **Why it shipped:** The commit's message described the new behaviour, but the function's comment still said "earliest", and the existing test only sets `stable_at`, so it could not detect the change. The image `main-65f7df6e` rolled out to the web and scheduler pods on Sep 2 at 18:14 UTC.
- **Fix:** `get_participant_role_time_seconds` uses `min(timestamps)` again. A new test, `test_case_cost_stops_at_earliest_status_timestamp`, covers an escalation followed by a stable transition and fails on the buggy code.
- **Secondary issue:** The hourly case cost job logged a TypeError for affected cases from Sep 8 onward. Projects with NULL `annual_employee_cost` or `business_year_hours` made `get_hourly_rate` fail, so those cases got no cost at all. `get_hourly_rate` now falls back to the project model defaults (50000 and 2080), and two new tests cover it. The logs don't name the affected projects, and I haven't established why those rows became NULL on Sep 8.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division, and a project with `business_year_hours = 0` still raises `ZeroDivisionError`.
- **Tests:** The full suite has 362 passing and 8 failing. The same 8 AI, database and entity tests fail on the original code too.

**Incident report fields**

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost