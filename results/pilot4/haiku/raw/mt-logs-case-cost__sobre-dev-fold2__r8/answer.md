## Recap

**Incident: inflated case response costs (finance warehouse)**

**Root cause:** `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` used `max()` instead of `min()` when choosing the cost cut-off from the stable, escalated and closed timestamps. The function's own comment said "earliest", and the cut-off should be the earliest. With `max`, a case that was closed or escalated after it was stable kept accruing participant time after stable. Case 5363 was flat at 2261 until it was marked stable on Sept 9, then jumped to 6241.

**Deploy:** commit `20f33137` (Jordan Lee, Sept 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") was built into image `main-65f7df6e` and rolled out to `dispatch-web` and `dispatch-scheduler` at 18:14–18:15 UTC on Sept 2. The first inflated cost in the sync was case 5284 on Sept 3 at 11:20 (3331 → 8804).

**Separate issue:** from Sept 8, the scheduler's hourly case-cost job logged a TypeError for some cases. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. The project's values were NULL, and the model defaults only apply on insert. I did not find what nulled those values on Sept 8.

**Changes (not committed or deployed):**
- `case_cost/service.py`: reverted the cut-off to `min(timestamps)`.
- `case_cost/service.py`: `get_hourly_rate` falls back to the project model's column defaults for a missing `annual_employee_cost` or `business_year_hours`. The defaults are read from `Project.__table__`, so they stay in sync with the model.
- `tests/case_cost/test_case_cost_service.py`: added `test_case_cost_stops_at_first_cutoff_timestamp` (fails on `max`: `7200.0 == 3600`) and `test_get_hourly_rate_uses_project_defaults_for_missing_values` (fails on the original code with the TypeError).
- `python -m pytest tests/case_cost`: 23 passed against the local PostgreSQL.

**Open items:**
- Costs already inflated in Dispatch and the finance warehouse need recalculating and a resync after the fix ships.
- The projects with NULL settings still need an owner to set real values.
- `incident_cost/service.py:131` has the same unguarded division. The scheduler log also shows an incident-cost task error. I did not change it.
- `business_year_hours = 0` would still raise a ZeroDivisionError. The fallback only covers `None`.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```