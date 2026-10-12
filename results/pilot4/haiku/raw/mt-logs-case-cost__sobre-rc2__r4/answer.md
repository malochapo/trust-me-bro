The post-deploy diffs are mostly normal accrual, with a few oddities I can't explain (some costs drop, and the bug can only raise them). Here's the recap, with the six lines at the end as requested.

**Recap: case response cost inflation and hourly TypeError**

- **Inflated costs.** Commit `20f33137d` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Accrual then ran to the latest of the escalated, stable, and closed timestamps, not the earliest. Cases that were escalated and later marked stable were overcharged. The change shipped in `main-65f7df6e` on 2025-09-02 at 18:14 UTC. Finance's warehouse is still carrying the inflated rows.
- **Inflated-cost date.** The first large inflation in the sync logs is on 2025-09-03 (case 5284, 3331→8804). I can't rule out a smaller inflation on the evening of September 2 from the logs alone, because normal accrual varies by project rate.
- **Hourly TypeError.** Some projects have `NULL` in `annual_employee_cost` or `business_year_hours`. `get_hourly_rate` divided without a fallback, so cases in those projects raised the error every hour. The likely cause is that those values were saved as `NULL` after insert, since model defaults only apply on insert. The logs don't name the project, and I haven't confirmed how the values became `NULL`. No deploy happened near September 8, which suggests a data change.
- **Fix (uncommitted).** `min` is restored, and `get_hourly_rate` falls back to the project model defaults (`DEFAULT_ANNUAL_EMPLOYEE_COST = 50000`, `DEFAULT_BUSINESS_YEAR_HOURS = 2080`), which are now shared constants in `project/models.py`.
- **Tests.** Two regression tests were added in `tests/case_cost/test_case_cost_service.py`. Both fail on the old code and pass on the fix. `python -m pytest tests/case_cost` passes (21 tests). The full suite has 8 failures that also fail on the unmodified code (AI service, one database test, one entity test), so I didn't touch them.
- **Open items.** `incident_cost/service.py` has the same unguarded division, and I haven't fixed it. Finance also needs the affected case costs recalculated and re-synced. The logs also show some case costs dropping, which I haven't explained.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```