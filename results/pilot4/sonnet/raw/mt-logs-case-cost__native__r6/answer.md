## Recap

**Cost inflation**
- Commit `20f33137` (Jordan Lee, 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). The cost cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` instead of the earliest.
- Image `main-65f7df6e` shipped it. The web and scheduler pods rolled to that image on 2025-09-02 at about 18:14–18:15Z. The previous image, `main-3e0445ff`, doesn't contain the commit. The later image `main-51546e13` (09-04) carries the bug too but didn't introduce it.
- case-cost-sync 1.5.0 was rolled out on 09-01 and isn't the cause.
- The first inflated case cost I can see in the cost-sync log is case 5284 on 2025-09-03 at 11:20Z, $3,331 to $8,804, flagged by the sync's own check. It is the only large positive jump between the deploy and that point, and it came after the deploy. Other flagged cases followed: 5327 (09-05), 5264 (09-08), 5363 (09-09) and 5406 (09-12).
- I can't rule out smaller inflation earlier on 09-02 or 09-03, because the logs don't carry case status or timestamps.
- Fix: back to `min`, plus the regression test `test_case_cost_uses_earliest_status_timestamp_as_cut_off`. It fails on the old code.

**Hourly TypeError**
- `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. The error text is `'NoneType' and 'int'`, so the `None` is the numerator, `annual_employee_cost`. The scheduler log shows 728 occurrences, starting 2025-09-08.
- The model's `default=` only applies on insert, so older rows can be NULL. I couldn't find which project is affected or why it started on 09-08, because the logs don't name the project.
- Fix: a missing value now falls back to the `Project` column default, which is 50000 for cost and 2080 for hours. The test is `test_get_hourly_rate__missing_project_settings_use_model_defaults`.
- The same unguarded division exists in `incident_cost/service.py:133`. I left it alone.

**Status:** both fixes and both tests are in the working tree, uncommitted. `tests/case_cost` passes, 21 of 21. Warehouse rows written since 09-03 should correct themselves on later syncs once the fix is deployed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost