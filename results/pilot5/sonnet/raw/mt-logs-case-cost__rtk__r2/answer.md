## Recap

**Cost inflation.** Commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function decides when a participant's time in a role stops counting.

- **Effect:** the cut-off moved from the earliest of `stable_at`, `escalated_at` and `closed_at` to the latest. Stable cases that also carried a later timestamp kept accruing cost, and the hourly scheduler job recomputed them.
- **Shipped:** the change went to production in image `main-65f7df6e` on 2025-09-02 at about 18:14 UTC. Production had been running `main-3e0445ff`, which doesn't contain it.
- **Timeline:** the first inflated cost I can see is case 5284 on 2025-09-03 at 11:20 UTC, 3331 → 8804, flagged by the finance job. No case had a rise over 400 between 2025-09-02 and that point. Earlier inflation under the 400 cutoff isn't ruled out.
- **Status:** fixed by reverting to `min`, and a regression test was added. The warehouse still holds inflated values from 09-02 onward, so it needs a recalculation and re-sync.

**TypeError since September 8.** `get_hourly_rate` divided a project's annual employee cost by its business year hours. Both are nullable columns, and their defaults only apply on insert.

- **Setting:** the error text was `'NoneType' and 'int'`, so the `None` was the dividend, which is `annual_employee_cost`. A missing `business_year_hours` would have produced `'int' and 'NoneType'`. The 708 tracebacks in the scheduler log all show the first form.
- **Status:** fixed. A missing value now falls back to the `Project` model's column default (50000 for the cost, 2080 for the hours), with a test.
- **Open question:** I couldn't tell which project lost its setting. If its real rates differ from the defaults, its case costs are still wrong.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost