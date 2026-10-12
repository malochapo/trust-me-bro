## Recap

**Incident:** Since 2025-09-02, case response costs in the finance warehouse have been inflated for some cases. Cases that were marked stable got a cost several times their correct value. Separately, since 2025-09-08 the hourly case cost job has logged a TypeError for some projects.

**Cost inflation (root cause):**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds`, from `min(timestamps)` to `max(timestamps)`.
- The function picks the cost cut-off from `stable_at`, `escalated_at` and `closed_at`. Its comment says the earliest of these should be used. With `max`, the cut-off moved to the latest of them, so participants kept accruing time after the case was stable.
- The first production rollout containing the commit was `main-65f7df6e`, at 2025-09-02 18:14Z.
- The first inflated sync was 2025-09-03 11:20Z (case 5284, 3331 → 8804). Other flagged cases followed: 5327, 5264, 5363 (the 9/9 case you reported) and 5406.
- Existing tests set only `stable_at`, so `min` and `max` gave the same result and the tests passed.

**Hourly TypeError:**
- `get_hourly_rate` in `src/dispatch/case_cost/service.py` computed `annual_employee_cost / business_year_hours` with no check. The log shows 708 TypeErrors from 2025-09-08 15:55 onward.
- The message `'NoneType' and 'int'` means `annual_employee_cost` was NULL. The model defaults (50000 and 2080) are insert-time defaults, so projects that already had NULL values never received them.

**Fixes (not committed):**
- `get_participant_role_time_seconds` uses `min` again.
- The model defaults are named constants in `src/dispatch/project/models.py`. `get_hourly_rate` falls back to them when a value is unset (`or`, so a stored 0 also counts as unset).

**Tests:**
- `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp` covers the cut-off. It fails with `max` and passes with `min`.
- `test_get_hourly_rate_uses_defaults_for_unset_project_values` and `test_calculate_case_response_cost_project_without_cost_settings` cover the fallback. Both fail on the old code.
- `tests/case_cost`, `tests/case_cost_type`, `tests/participant_role`, `tests/project` and `tests/incident_cost` all pass with the fixes.

**Open items:**
- The same unguarded `get_hourly_rate` exists in `src/dispatch/incident_cost/service.py:131`. The incident cost job would hit the same TypeError for NULL projects. I haven't changed it.
- The cost values already in the warehouse are not corrected. That needs a recalculation through the finance sync, which I have not run.
- The logs don't name the affected projects, so I haven't checked which production projects have NULLs.
- The traceback paths are from the installed package. I assumed it matches this checkout.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```