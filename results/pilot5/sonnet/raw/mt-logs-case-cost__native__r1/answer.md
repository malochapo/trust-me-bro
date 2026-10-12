## Recap

**Cost bug.** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", committed 2025-09-02 09:29 PDT) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function gathers `stable_at`, `escalated_at` and `closed_at` to decide where a case's cost stops. With `max`, cost kept accruing until the latest of those timestamps, so cases with more than one of them were re-priced upward. Rates and cost models never changed.

**Deploy.** The fix first reached production in the Dispatch deploy of `main-65f7df6e` on 2025-09-02 at about 18:14 UTC. `main-51546e13` on 2025-09-04 also contained it. The earlier deploy `main-3e0445ff` (2025-08-27) did not.

**Impact.** The first inflated cost is case 5284 on 2025-09-03 at 11:20 UTC (3331 to 8804). No jump of that size appears between the deploy and that sync. Later jumps:
- 5327: 2244 to 5539 on 09-05.
- 5264: 3285 to 11987 on 09-08.
- 5363: 2261 to 6241 on 09-09.
- 5406: 1975 to 4945 on 09-12.

The sync also flagged 5406 on 09-12 at 11:20, a fifth flagged case I hadn't listed before.

Smaller inflations happened on other cases and aren't in this list. I checked jumps of more than 30% and more than $400, which is a threshold I picked, not a log field.

**Fixes (in the working tree, not committed or deployed).**
- The bug is reverted to `min`, with a regression test, `test_case_cost_stops_at_earliest_status_timestamp`.
- The separate hourly TypeError (708 occurrences since 2025-09-08 15:55) came from a project with `annual_employee_cost` NULL. `get_hourly_rate` now falls back to the project model's defaults of 50000 and 2080. Its test is `test_get_hourly_rate__missing_values_use_project_defaults`.

**Follow-ups.**
- Deploy the fix.
- Have finance re-sync the affected cases.
- Check which project has the NULL cost setting.
- A `business_year_hours` of 0 would still divide by zero.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost