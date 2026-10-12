Recap of the incident:

- **Cost inflation:** commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed the participant-time cut-off from the earliest end event to the latest. A case escalated and later marked Stable was charged for the whole escalated period again. That window belongs to the incident. The change shipped in dispatch image `main-65f7df6e`, rolled out Sep 2 at 18:14–18:15 UTC. The first flagged inflated case was 5284 on Sep 3. I did not check the logs for earlier unflagged inflation, so Sep 3 is the first flagged date, not a proven first date.
- **Fix:** the cut-off is back to `min` (`src/dispatch/case_cost/service.py`), with a regression test that fails on the buggy code.
- **Hourly TypeError:** `get_hourly_rate` divided by project values that were NULL. The error reads `'NoneType' / 'int'`, so the NULL is `annual_employee_cost`. The project update path can write explicit nulls. Cost now falls back to the model defaults, with a test.
- **Not yet done:** both fixes are uncommitted. `incident_cost/service.py` has the same unguarded division. Project updates can still store NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost