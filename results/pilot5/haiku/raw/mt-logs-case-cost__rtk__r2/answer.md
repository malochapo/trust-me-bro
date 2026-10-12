Here is the recap for the incident report. The fixes are in the working tree and not yet committed or deployed.

**Incident recap**

- **Inflated costs:** after commit `20f33137` shipped on Sep 2 (image `main-65f7df6e`), participant time for cases that were escalated and later marked Stable ran until Stable instead of stopping at escalation. The cost-sync job flagged the first such case, 5284, on Sep 3 at 11:20 (3331 → 8804). The Stable jumps then continued (5327, 5264, 5363, 5406). Case 5363 went from 2261 to 6241 on Sep 9. The Sep 2 evening diffs for 5346 and 5349 are small, so I've treated Sep 3 as the first confirmed inflated cost, but I haven't ruled those two out.
- **Root cause:** `get_participant_role_time_seconds` used `max(timestamps)` where the earlier code used `min`. The code comments and the renounce check both describe the earliest-timestamp behaviour, so the commit title ("latest status timestamp") contradicts the code's intent. The fix restores `min`. A regression test covers an escalated-then-stable case, and it fails under `max`.
- **Ruled out:** the cost-sync 1.5.0 upgrade on Sep 1. Its log output is unchanged, and it only copies values from Dispatch.
- **Scheduler TypeError (from Sep 8):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with a `NULL` annual employee cost raised `TypeError` on every hourly run, so their cases got no cost. Those cases now fall back to the model defaults of 50000 and 2080. The cause of the `NULL`s is unknown. The logs don't name the projects, and no commit in the window touches these fields. The SQL query to find affected projects is in the earlier summary.
- **Still open:** `incident_cost/service.py:133` has the same unguarded division, so incidents in those projects will fail the same way. The Sep 1 to Sep 14 warehouse values also need re-syncing after the fix ships.
- **Tests:** `tests/case_cost` passes (22). The full suite has 362 passed and 8 failed. Those 8 also fail without my changes, in `tests/ai`, `tests/database` and `tests/entity`.

```text
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```