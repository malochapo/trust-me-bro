The earliest large inflated cost is the Sept 3 entry for case 5284, so FIRST_INFLATED is 2025-09-03. Smaller increases on Sept 2 would fall under my 300-unit threshold, so that date is the first large one, not a proven first. Here's the recap.

## Recap

**Cost inflation (the cost bug)**
- **Cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Participant role time was counted until the latest of escalated, stable, or closed, not the earliest. Marking a case stable could then extend the billable window, which is why costs jumped at that point. The function's own comment said "earliest".
- **Shipped:** image `main-65f7df6e`, rolled out 2025-09-02 at about 18:15 UTC. The scheduler was on that image from 18:15:24.
- **Symptom:** the finance warehouse showed large jumps for Stable cases, for example case 5363 going from 2261 to 6241 on Sept 9. The first large jump was case 5284 on Sept 3.
- **Fix:** restored `min(timestamps)`. Added `test_case_cost_stops_at_first_cut_off_event`, which fails on the buggy code (7200 vs 3600 seconds) and passes with the fix.
- **Not verified:** I didn't reproduce the calculation or check how many warehouse rows are affected. Those rows will need recalculating.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours` without a null check. The traceback shows `NoneType` on the left, so the missing setting is `annual_employee_cost`. The log has 708 of these, starting 2025-09-08 15:55.
- **Fix:** missing values fall back to the project model defaults, 50000 and 2080. The defaults are now named constants in `project/models.py`. Added four parametrized tests for the fallback and one end-to-end test with NULL fields. The tests fail on the old code and pass with the fix.
- **Effect:** cases in those projects now get costs at the default rate of 25/hour. Finance should expect those figures to change.
- **Not changed:** `incident_cost/service.py` has the same unguarded division, so the incident cost job can hit the same TypeError.

**Test results:** `tests/case_cost`, `tests/case`, `tests/project`, and `tests/incident_cost` pass (61 tests). I didn't run the full suite.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```