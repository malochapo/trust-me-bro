Here is the recap for the incident report. The six lines are at the end, in the requested form.

**What happened**
- Costs for stable cases roughly doubled or tripled starting Sept 3. Case 5363's classic cost went from 2261 to 6241 on Sept 9.
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Sept 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function's comment and the original code (`200cd428`) use the earliest milestone. With `max`, a case's role time runs until its latest milestone (stable, escalated or closed), not the earliest.
- That commit reached production in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on Sept 2 at 18:14–18:15 UTC. The image was replaced by `main-51546e13` on Sept 4 at 16:52, which still included the change.

**Fix 1 (cost inflation):** reverted `max` to `min` at `src/dispatch/case_cost/service.py:353`. Regression test `test_case_cost_stops_at_earliest_milestone` fails with `max` (7200 vs. 3600 seconds) and passes with `min`.

**Fix 2 (hourly TypeError):** `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours`. Projects with NULL in either column raised `TypeError` for every case on each hourly run. The scheduler caught it per case, so the rest of the run continued. The function now uses the project model's column defaults (50000 and 2080) when a value is `None`. Three tests cover this (`test_get_hourly_rate*`). The two NULL-case tests fail on the original code and pass with the fix.

**Verification:** `tests/case_cost` and `tests/incident_cost` pass against the local PostgreSQL (38 tests). I ran them in a clean venv I created at `run-77806e94c2e0/test-venv`, because the existing venv couldn't import `slack_sdk`.

**Caveats for the report**
- `FIRST_INFLATED` is based on the first large step change in `cost-sync.log` after the deploy, which is case 5284 on Sept 3 at 11:20 (3331 → 8804). Earlier diffs after the deploy are hourly growth on active cases, not step changes. A case that became stable or escalated in that window could be an earlier inflated one, but the logs don't show case timestamps to check.
- I don't know which projects have NULL values. The logs show only the error, not the project.
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` pattern and I didn't change it. I also haven't checked the logs for TypeErrors from the incident cost job.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost