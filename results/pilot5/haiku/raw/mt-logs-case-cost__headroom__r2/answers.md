**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee) changed one line in `src/dispatch/case_cost/service.py` (`get_participant_role_time_seconds`, around line 353). It changed `min(timestamps)` to `max(timestamps)`. The `timestamps` list holds the case's `stable_at`, `escalated_at` and `closed_at`. Under `min`, participant time was cut off at the earliest of those. Under `max`, it is cut off at the latest.

**Effect:** for a case that was escalated and later marked stable, the cut-off moves from the escalation time to the stable time. Every participant's time in the escalation-to-stable window is then billed. The cost is inflated and the cut-off no longer matches the function's own comment ("Determine the earliest relevant timestamp for cost calculation cut-off").

**Evidence for case 5363:**
- Its classic cost climbs about 145 per hour from Sept 4, then stops at 2261 around Sept 5 (cost-sync.log has no diff lines for it from Sept 5 to Sept 9). A frozen value is what the `min` cut-off produces once the case has been escalated.
- At 2025-09-09T12:20 it jumps 2261 → 6241, the run after the case was marked stable. Under `max`, the cut-off moves to `stable_at`.
- The other flagged cases follow the same pattern: 5284 (Sept 3), 5327 (Sept 5), 5264 (Sept 8), 5406 (Sept 12). Each is a Stable case with a jump of 147–265% in one run. The first is Sept 3, the first run after the deploy below.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, which contains `20f33137` as an ancestor. `events.log` shows it rolled out to `dispatch-web` and `dispatch-scheduler` starting at 2025-09-02 18:14 UTC. The earlier production image, `main-3e0445ff` (rolled out Aug 27), predates the commit in the history.

**Caveats:**
- I did not run tests or reproduce the arithmetic. The conclusion rests on the diff, the frozen-then-jump pattern, and the timing.
- The logs don't show case 5363's `escalated_at` or `stable_at` values, so the escalation step is inferred.
- The commit message says "latest status timestamp", but the code only looks at `stable_at`, `escalated_at` and `closed_at`. The mismatch is worth raising with the author, since `min` matches the code comment.

No code has been changed. A likely fix is to revert `max` to `min`, but that needs a decision from you and a test that covers an escalated-then-stable case.

----- next turn -----

I reverted the `max` back to `min` in `get_participant_role_time_seconds` and added a regression test. The `tests/case_cost` suite passes (20 tests, using `python -m pytest`).

**The fix** (`src/dispatch/case_cost/service.py`, line 353): the cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at` again. The function's comment already said "earliest", so this matches the original intent.

**The test** (`tests/case_cost/test_case_cost_service.py`): `test_participant_role_time_stops_at_earliest_cutoff`. It sets up an assignee assumed 3 hours ago, a case escalated 2 hours ago, and a case marked stable 1 hour ago. It expects 3600 seconds, the time up to escalation. The existing stable-cut-off test only set `stable_at`, so it could not catch this bug.

I confirmed the test catches the bug: with `max()` restored it fails, and I put `min()` back afterwards.

I did not run the linter because `ruff` is not installed in this environment. The only change to the source is the one-line fix. The existing 19 tests in the file still pass alongside the new one.

Nothing is committed. The cost data already written to the finance warehouse, including the flagged cases (5284, 5327, 5264, 5363, 5406), still carries the inflated values. Correcting those rows is a separate step, and I have not touched it.

----- next turn -----

The hourly `TypeError` came from projects whose `annual_employee_cost` or `business_year_hours` is `NULL`. Those cases now get a cost from the project model defaults, and the new tests pass.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. When either is `NULL`, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler logged 708 of these in the window, starting 2025-09-08 around 15:55. The columns are nullable, and the model's `default=` only applies on insert, so rows that already have `NULL` never pick up the default.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic schema use them, so the values exist in one place.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes each default when its value is `None`. It checks `is None`, not falsiness, so a real `0` still reaches the division.

**Tests** (`tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers a missing cost, a missing hours value, and both missing.
- `test_calculate_case_response_cost_classic_project_without_cost_settings` runs the classic cost calculation for a project with both values set to `None`, and expects the default rate of 25 per hour for one hour of assignee time.

I checked that both new tests fail on the old `get_hourly_rate`. `python -m pytest tests/case_cost tests/incident_cost tests/project` passes: 43 tests.

**Not done:**
- I did not find out how these projects got `NULL` values, or why the errors started on September 8. The logs don't name the projects. Finding them would need a query such as `SELECT id, name FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL`. That query may also be worth running against production to see how many projects are affected.
- `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` with the same bug. I left it alone because you asked about the case cost job, but it would fail the same way for incidents in those projects.
- Nothing is committed.

----- next turn -----

Here is the recap for the incident report.

**Cost inflation (the main incident)**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Sept 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off for participant time then moved from the earliest of escalated/stable/closed to the latest. For a case escalated before it was marked stable, participants were billed through the whole escalation-to-stable window.
- It shipped in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` from 2025-09-02 18:14 UTC.
- Case 5363 shows the pattern: its classic cost stayed at 2261 from about Sept 5 until Sept 9, when it was marked stable and the cost jumped to 6241. The cost-sync job flagged five stable cases this way (5284, 5327, 5264, 5363, 5406).
- Fix: reverted to `min(timestamps)`, with a regression test (`test_participant_role_time_stops_at_earliest_cutoff`) that fails on the `max` version.

**Hourly TypeError**
- `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. For projects where the value was `NULL`, that raised the TypeError, so their cases got no cost. The scheduler logged 708 of these.
- Fix: the defaults (50000 and 2080) are named constants in `project/models.py`. `get_hourly_rate` uses them when a value is `None`. Two regression tests cover this.

**Open items**
- Nothing is committed.
- The rows already written to the finance warehouse still hold the inflated values. Those need correcting separately.
- `incident_cost/service.py` has the same `get_hourly_rate` and will raise the same TypeError for incidents in those projects. I did not change it.
- I did not find out why some projects have `NULL` settings, or which projects they are.
- FIRST_INFLATED is based on the first large jump the cost-sync job flagged. Smaller inflation may have started earlier. Sept 2 diffs before the 18:14 rollout look normal, and I did not check whether any Sept 2 changes after it were inflated.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```