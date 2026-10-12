The recap is below. The fix is in the working tree and not committed or deployed, and the warehouse values are not corrected yet.

**Summary**

- **Inflated case costs (cost bug):** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off is built from `stable_at`, `escalated_at` and `closed_at`, and the function's comment says it should be the earliest. With `max`, a case that was escalated and later marked stable was billed for the time between those two events. The change shipped in `main-65f7df6e`, which went live on 2025-09-02 at 18:14 UTC. The first inflated cost was case 5284 on 2025-09-03. Later flagged cases were 5327, 5264, 5363 and 5406.
- **Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. Projects with `annual_employee_cost` unset raised the error on every hourly run from 2025-09-08 onward, 708 times in total. The fix uses the project model's defaults (50000 and 2080) for missing values.
- **Fixes in the working tree (uncommitted):**
  - `src/dispatch/case_cost/service.py`: `min` restored, and `get_hourly_rate` falls back to defaults.
  - `src/dispatch/project/models.py`: defaults are named constants.
  - `tests/case_cost/test_case_cost_service.py`: three new regression tests. Each fails on the old code and passes with the fix. All 22 case-cost tests pass.

**Open items**

- Warehouse rows for the flagged cases still show inflated values. Finance needs to decide on a backfill.
- `incident_cost` has the same `get_hourly_rate` with no fallback. Its logs show no TypeError, but projects with these values unset would fail there too.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```