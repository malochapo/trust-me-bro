**Recap**

- **Cost inflation:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` when picking the cost cut-off in `get_participant_role_time_seconds`. The cut-off is the earliest of the case's `stable_at`, `escalated_at` and `closed_at`. Using the latest let costs keep accruing past the point where they should have stopped, so finance's warehouse received inflated totals.
- **Deploy:** it first reached production in image `main-65f7df6e`, rolled out on 2025-09-02 at about 18:14Z. The previous image, `main-3e0445ff`, did not contain the change. `main-51546e13` (09-04) also contains it, but it didn't introduce it.
- **Timeline:** the first inflated cost reached the warehouse in the 2025-09-03 11:20Z sync (case 5284, 3331→8804). No case jumped like that before the deploy. The one I read in detail, your example case 5363 (2261→6241 on 09-09), is the third of five flagged jumps.
- **Hourly TypeError:** the `Project` model's `annual_employee_cost` and `business_year_hours` columns are nullable, so some project has NULL for one or both, and `get_hourly_rate` divides by None. The log doesn't say which project or which of the two settings is missing. I couldn't identify what changed on September 8, and the SQL check I suggested earlier would show which project it is.
- **Fixes (uncommitted):** `min()` is restored with a regression test. `get_hourly_rate` now falls back to the project model defaults (50000 / 2080), with tests. The case_cost, project and incident_cost tests pass. `incident_cost/service.py` has the same unguarded division and is untouched.
- **Still to do:** deploy the fix, recompute the stable cases that were already inflated (the scheduler skips stable cases updated after `stable_at`), and have finance re-sync those rows.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours (the logs don't say which; the code can't divide when either is NULL)