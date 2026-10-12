Here's the recap for the incident report. Nothing is committed or deployed yet.

**Incident: inflated case response costs**

- **Cause:** On 2025-09-02, commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets where a participant's time stops counting. The earliest of `stable_at`, `escalated_at` and `closed_at` is the correct cut-off, and the function's own comments say so. With `max`, cost ran to the latest of those events, so a case that was escalated and later marked stable kept accruing cost between the two. Rates and cost models were unchanged.
- **Shipped:** the `main-65f7df6e` image, rolled out to production on 2025-09-02 at about 18:15 UTC. The scheduler ran it until 2025-09-04, when `main-51546e13` replaced it.
- **Evidence:** the first flagged jump was case 5284 on 09-03, from 3331 to 8804. Case 5363 went from 2261 to 6241 on 09-09, when it was marked stable. The logs can't show the first inflated cost to the hour, so FIRST_INFLATED uses the first flagged jump. Inflation may have started on the evening of 09-02.
- **Fix:** `min` is restored. Regression test: `test_case_cost_stops_at_first_status_change`. It fails with `max` and passes with `min`.

**Separate issue: hourly TypeError (708 errors, 2025-09-08 to 09-14)**

- **Cause:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for NULL. The model's `default=` applies only on insert, so projects with NULL values stayed NULL and their cases were skipped every hour.
- **Fix:** both values fall back to the model defaults, 50000 and 2080, which are now named constants in `project/models.py`. The same fix covers the identical function in `incident_cost`. Tests: `test_get_hourly_rate_uses_project_defaults_when_missing` and `test_calculate_case_response_cost_new_with_missing_project_values`. Both fail on the old code and pass now.
- **Open:** the logs don't name the affected projects, and I haven't found how their settings became NULL.

**Verification:** `python -m pytest tests/case_cost tests/incident_cost tests/project` gives 43 passed. I didn't run the full suite, and `ruff` isn't installed here.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost