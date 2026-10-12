## Recap

**1. Inflated case costs (classic and new cost models)**
- **Cause:** commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from the earliest of the stable, escalated and closed timestamps to the latest. For a case that was escalated and later marked stable, the cut-off moved from the escalation time to the stable time. The cost jumped retroactively, and the cost-sync job copied it to the warehouse.
- **Shipped by:** image `main-65f7df6e`, rolled out to the scheduler on 2025-09-02 at 18:14–18:15 UTC. The later images `main-51546e13` (Sept 4 and Sept 10) also contain the commit.
- **Evidence:** five cases (5264, 5284, 5327, 5363, 5406) had their cost frozen at escalation, then jumped on the first hourly run after they were marked stable.
- **Fix:** restored `min(timestamps)`. Added `test_get_participant_role_time_seconds_stops_at_first_cutoff_event`. It fails on the old `max` code.
- **Not yet done:** the warehouse rows for those five cases still hold the inflated values and need a re-sync.

**2. Hourly TypeError (cases with no cost, since Sept 8)**
- **Cause:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Some projects have NULL in `annual_employee_cost`, because the model default only applies on insert. Each affected case raised during the hourly run, and the error was logged and skipped.
- **Fix:** `get_hourly_rate` now falls back to the model defaults (50000 and 2080), which are now named constants in `project/models.py`. Added two tests. Both fail without the fallback.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division. It is not in the logs, but it would fail the same way.

**Verification:** `tests/case_cost` passes (22 tests). `tests/project`, `tests/case`, `tests/incident_cost` and `tests/case_cost` together pass (58 tests). Nothing is committed.

**Caveats for the report:**
- `FIRST_INFLATED` is the first date an inflated value appears in the logs (the Sept 3 run). The logs don't show escalation times, so a case inflated on the evening of Sept 2 couldn't be ruled out.
- The escalation timestamps for the five cases were inferred from the freeze pattern, not read from the database.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```