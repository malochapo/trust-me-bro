Here's the recap for the incident report.

**Summary**

- **Symptom:** case response costs for Stable cases jumped several times over in one sync, for example dispatch-default-security-5363 went from $2,261 to $6,241 on Sep 9. Nothing in the rates or cost models changed.
- **Root cause:** commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For a case past triage, the cost cut-off moved from the first status change (escalated, stable or closed) to the last. When a case turned Stable, every participant's hours were counted up to `stable_at`, so the cost jumped at that point. Active cases were unaffected, so costs only inflated once a case went Stable.
- **Deploy:** `main-65f7df6e`, rolled out to dispatch-web and dispatch-scheduler on Sep 2 at 18:14 UTC. `main-51546e13` on Sep 4 also contains the change but did not introduce it.
- **Fix:** restored `min(timestamps)`. Added two regression tests in `tests/case_cost/test_case_cost_service.py`; both fail on the buggy code (7200 s instead of 3600 s) and pass with the fix.
- **Separate issue:** the hourly case cost job logged a TypeError for 708 cases from Sep 8. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for NULL. A project with either value NULL raised an error, and the case was skipped every hour. Fix: fall back to the project model defaults (50000 and 2080). Added a parametrized test, which fails on the old code for the three missing-value cases.
- **Not yet resolved:**
  - Affected cases already in the finance warehouse still need a backfill or rerun.
  - The projects with NULL settings are not identified in the logs; use the query in my earlier note to find them.
  - `incident_cost/service.py` has the same unchecked division, so incident costs can fail the same way. Not changed.
  - Full suite: 8 failures on the original code too, in AI, database and entity tests.
  - Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours