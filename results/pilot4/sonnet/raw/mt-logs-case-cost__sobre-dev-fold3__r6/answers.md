**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`).

That function picks the time at which a participant's cost stops accruing. The code comment still says "Determine the **earliest** relevant timestamp for cost calculation cut-off". It takes the case's `stable_at`, `escalated_at` and `closed_at` and, until this commit, used the earliest, so cost stopped when the case first left active handling. With `max()` it uses the latest one, so a case with more than one of these timestamps keeps accruing cost for every participant role that has not been renounced. The hourly rates and cost models are unchanged. Only the cut-off moved later, so cost is counted over a longer period. That matches the multiples you're seeing, and `case_cost/scheduled.py` writes the larger amount to the DB, which the API then serves.

**The deploy:** `main-65f7df6e`, rolled out on 2025-09-02 at about 18:14Z. `events.log` shows:
- The `dispatch-db-upgrade-65f7df6e` job ran at 18:14:09Z.
- The scheduler pulled `main-65f7df6e` at 18:15:10Z.
- Web pulled `main-65f7df6e` at 18:14:37Z.

`65f7df6e` is the first production image that contains `20f33137`. The image before it, `main-3e0445ff` (deployed 2025-08-27), does not. Image tags are commit SHAs, and I confirmed the ancestry with git. The later `main-51546e13` deploy on 09-04 also contains the change, but it isn't the one that introduced it.

**Evidence from the logs:**
- `cost-sync.log` has zero flagged cases from 08-25 to 09-02, with costs growing steadily at about $145/h.
- Starting right after the deploy, five stable cases jump by 147–265% in a single sync and get flagged:
  - 5284 on 09-03: 3331→8804
  - 5327 on 09-05
  - 5264 on 09-08
  - 5363 on 09-09: 2261→6241
  - 5406 on 09-12
- Before the deploy, stable cases froze at their cut-off value. Case 5284, for example, stayed at 3331 for days.

**Ruled out:**
- case-cost-sync 1.4.2→1.5.0 on 09-01 10:20Z. It predates the deploy, and nothing was flagged for two more days.
- The `TypeError` in the scheduler log (`annual_employee_cost` is None for some project). It starts 09-06 and skips the cost update for those projects' cases rather than inflating costs. It's a separate bug worth its own ticket.
- The 09-10 scheduler pod restart. It pulled the same image.

**One gap:** I haven't pinned down why each frozen stable case was recomputed on the specific day it jumped. That would need the case's status history from the database, where each case's `stable_at`, `escalated_at` and `closed_at` values would confirm the mechanism. The `min`→`max` change, its deploy time and the onset of the jumps line up on their own.

**Suggested next steps (no code changed yet):**
1. Revert `20f33137`, or restore `min()`, and redeploy.
2. Have the scheduler recompute the affected stable cases and tell finance to re-sync them.
3. Consider why the original commit wanted "latest", since it may have been aiming at a real edge case.

----- next turn -----

I restored `min()` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`), so the cost cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at` again. I haven't committed anything.

I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It builds a stable case that also has later `escalated_at` and `closed_at` values and an active role. It asserts that cost stops at `stable_at`, the earliest timestamp.

With the fix, all 20 tests in `tests/case_cost` pass. With only the source change stashed (the old `max()` back in), the new test fails and the other 19 still pass. So the existing suite did not cover this case and the new test does.

The fix only helps once it is deployed. I haven't touched the cases that were already inflated. Stable cases whose stored cost is too high will only be corrected if the scheduler recomputes them. The scheduler skips a stable case whose cost was updated after `stable_at`, so those cases probably need a manual recompute. Finance will also need to re-sync the affected rows.

----- next turn -----

The TypeError is fixed and has a test. The fix only takes effect once deployed. Nothing is committed.

**Cause:** `get_hourly_rate` in `case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns on `Project` are nullable, and their default of 50000 / 2080 is only applied when a row is inserted. A project whose values were saved as NULL raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. Because the exception is raised before the cost is saved, the scheduler skips every case in that project, and it logs the error again every hour. The scheduler log shows the first such error on 2025-09-08 at 15:55, which fits the "since September 8" you saw.

**What I couldn't determine:** which project has NULLs, and what changed on September 8. The logs don't say. I'd check `SELECT id, name FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL`.

**Fix:**
- `get_hourly_rate` now replaces only the value that is missing with the project model's default (50000 for the annual cost, 2080 for the business-year hours). A project with one value set keeps it.
- To avoid copying the numbers, I added `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS` to `project/models.py`. The SQLAlchemy columns and the pydantic schema now use those constants. The values are unchanged.

**Tests**, added to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_values_use_defaults` covers both values missing and each one missing on its own.
- `test_calculate_case_response_cost__project_without_rate_inputs` runs the full cost calculation on a project with both values NULL.

`tests/case_cost`, `tests/project` and `tests/incident_cost` pass together (43 tests). With the `src/dispatch/case_cost` changes stashed, both new tests fail. That stash also removed the earlier `min()` fix, so the earlier regression test failed too.

**Not changed:** `incident_cost/service.py:131` has the same unguarded division. Incident costs aren't in your logs, so I left it alone, but a project with NULLs would break there too. I can apply the same fix if you want.

----- next turn -----

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