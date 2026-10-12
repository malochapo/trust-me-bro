Here is the recap for the incident report.

**Cost inflation (the main incident)**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Sept 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off for participant time then moved from the earliest of escalated/stable/closed to the latest. For a case escalated before it was marked stable, participants were billed through the whole escalation-to-stable window.
- It shipped in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` from 2025-09-02 18:14 UTC.
- Case 5363 shows the pattern: its classic cost stayed at 2261 from about Sept 5 until Sept 9, when it was marked stable and the cost jumped to 6241. The cost-sync job flagged five stable cases this way (5284, 5327, 5264, 5363, 5406).
- Fix: reverted to `min(timestamps)`, with a regression test (`test_participant_role_time_stops_at_earliest_cutoff`) that fails on the `max` version.

**Hourly TypeError**
- `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. For projects where the value was `NULL`, that raised the TypeError, so their cases got no cost. The scheduler logged 708 of these.
- Fix: the defaults (50000 and 2080) are named constants in `project/models.py`. `get_hourly_rate` uses them when a value is `None`. Two regression tests cover this.

**Open items**
- Nothing is committed.
- The rows already written to the finance warehouse still hold the inflated values. Those need correcting separately.
- `incident_cost/service.py` has the same `get_hourly_rate` and will raise the same TypeError for incidents in those projects. I did not change it.
- I did not find out why some projects have `NULL` settings, or which projects they are.
- FIRST_INFLATED is based on the first large jump the cost-sync job flagged. Smaller inflation may have started earlier. Sept 2 diffs before the 18:14 rollout look normal, and I did not check whether any Sept 2 changes after it were inflated.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```