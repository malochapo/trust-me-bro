The earlier ratio check is noisy, and large jumps also appear before the deploy, so it can't date the first inflated cost precisely. I'll use the earliest inflation I could tie to the bug (the 2025-09-03 flag) and note the caveat.

## Incident recap

**Symptom:** Since early September, the finance warehouse received case response costs several times higher than the previous hour, for Stable cases with no rate or model change. Example: `dispatch-default-security-5363` went from $2,261 to $6,241 on 2025-09-09. Separately, the scheduler's hourly case-cost job logged a TypeError for some cases from 2025-09-08.

**Root cause 1 (inflated costs):** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off for a case's participant time is now the latest of stable, escalated and closed rather than the earliest. Cases that were escalated and later marked stable accrued cost up to the stable mark. The function's own comment and the existing stable-time test both describe the earliest-timestamp behaviour. Shipped in `registry.example.com/dispatch:main-65f7df6e`, rolled out 2025-09-02 18:14 UTC; still live via `main-51546e13` (2025-09-04). Fixed by reverting to `min`, with a regression test that fails on the old code.

**Root cause 2 (TypeError):** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Projects with NULL in either column (the model defaults apply only on insert) raised TypeError, so those cases got no cost. Fixed by falling back to the model defaults (50000 and 2080), with a regression test.

**Caveats for the report:**
- The first inflated cost is not conclusively dated. The earliest flagged inflation is 2025-09-03; large jumps also appear before the deploy, so I can't attribute them to the bug.
- Affected finance rows need recomputing from 2025-09-02 for the inflation bug. The TypeError cases also need recomputing, but I didn't identify which projects they were.
- `incident_cost/service.py:133` has the same unguarded division and is not fixed.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours (project-level NULL; the TypeError is raised by get_hourly_rate, which uses both)