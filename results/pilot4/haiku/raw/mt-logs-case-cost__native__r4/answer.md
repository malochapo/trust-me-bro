I checked each case's post-deploy deltas against its own normal rate. The earliest real step is case 5284 on Sep 3 at 11:20 UTC. The Sep 2 19:20 value is within normal noise, so I'm using Sep 3 as the first inflated date.

## Recap

**Inflated costs (the cut-off bug):** Commit `20f33137` changed the participant-time cut-off in `get_participant_role_time_seconds` from `min(...)` to `max(...)`. Time was then counted from escalation until stabilization or closure instead of stopping at the first status change. That produced step increases when escalated cases were marked stable or closed (5284, 5327, 5264, 5363, 5406). It shipped in image `main-65f7df6e`, rolled out to production on 2025-09-02 at 18:14–18:15 UTC. The fix restores `min(...)`, and a new test fails on `max` and passes on `min`.

**Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with a `NULL` value for these settings hit `None / int`, so the case-cost job skipped those cases each hour from Sep 8. The fix falls back to the project model's defaults (50000 and 2080), and new parametrized tests cover each missing-value case.

**Not covered by this fix:** `incident_cost/service.py` has the same division without a fallback. It isn't logging errors, but it would fail the same way for a project with a `NULL` value.

**Still open:** Nothing is committed yet. Warehouse rows for the affected cases still need recomputing after the fix ships. The eight failing tests in AI, restricted case filter and entity search predate this work.

The six fields for the report:

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost