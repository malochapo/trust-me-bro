The first inflated case in the logs is case 5284, on 2025-09-03. The 5345 line the filter caught is ordinary hourly growth on a low base, not a jump.

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`, where `timestamps` holds `stable_at`, `escalated_at` and `closed_at`. The cost cut-off therefore moved from the earliest of those times to the latest.
- **Effect:** a case that was escalated froze its cost at `escalated_at`. When it was later marked stable or closed, the cut-off jumped forward and all the time in between was billed at once.
- **Deploy:** this reached production with the Sep 2 rollout of `registry.example.com/dispatch:main-65f7df6e` at about 18:14Z.
- **Evidence:** the sync flagged five cases, each in Stable state: 5284, 5327, 5264, 5363 and 5406. The first was 5284 on Sep 3 ($3,331 to $8,804).
- **Fix:** I restored `min()` and added `test_case_cost_stops_at_earliest_status_timestamp`. That test fails with `max()` and passes with `min()`. Warehouse rows already written for the affected cases still need a re-sync.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`, and both columns are nullable. The traceback says `NoneType / int`, so the left operand, `annual_employee_cost`, was the missing one. I couldn't see why it first appeared on Sep 8.
- **Fix:** a missing value now falls back to the `Project` model default, with a test, `test_get_hourly_rate_uses_project_defaults_when_unset`.
- **Same bug elsewhere:** `incident_cost/service.py` has the same unguarded division, and I didn't change it.

Both fixes are uncommitted, and the 21 tests in `tests/case_cost` pass.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost