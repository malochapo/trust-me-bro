**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", 2 Sep 2025) changed one line in `src/dispatch/case_cost/service.py`, in `get_participant_role_time_seconds`. It changed `min(timestamps)` to `max(timestamps)`. For cases not in New or Triage, the function takes the timestamps of `stable_at`, `escalated_at` and `closed_at` and uses them as the cut-off for billable participant time. The original `min` stopped billing at the first of those. `max` stops billing at the last one. The function's own comment still says "earliest relevant timestamp", so the change contradicts the code's stated intent. A case that is marked Stable after an earlier escalation or closure now bills participant time up to the later timestamp. That is how case 5363 jumps.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out to `dispatch-web` at 2025-09-02 18:14Z (11:14 PT). The image includes `20f33137`, which is an ancestor of `65f7df6e` on `main`. The scheduler was redeployed with the same image at 18:15Z. No other dispatch rollout falls between that deploy and the first anomaly.

**Evidence from the logs:**
- The large increases in `cost-sync.log` (over 300 in one run) are confined to six cases. All of them start on 3 Sep and later, after the 2 Sep rollout. The first is case 5284 on 3 Sep 11:20Z (3331 → 8804). The rest are 5327 (5 Sep), 5264 (8 Sep), 5363 (9 Sep, 2261 → 6241) and 5406 (12 Sep). Every one is a Stable case, and every one is flagged by `costsync.checks`.
- Case 5363 shows the pattern clearly. Its classic cost is frozen at 2261 from 5 Sep 16:20 until 9 Sep 12:20, then jumps to 6241. A frozen value followed by a jump is what a cut-off that moves to a later timestamp would produce.
- Before 2 Sep there are no equivalent increases. The only flagged warning before then is an unrelated Retry warning on 31 Aug.

**Ruled out:**
- *cost-sync 1.5.0*: the finance job moved from 1.4.2 to 1.5.0 on 1 Sep 10:20Z. Its runs from 1 to 2 Sep report 0 flagged and show the same normal hourly deltas as 1.4.2, so it does not explain the spikes.
- *The 4 Sep deploy (`main-51546e13`)*: the first flagged case is on 3 Sep, before that deploy.

**Gaps:**
- I have not queried the Dispatch database. The stable/escalated/closed timestamps for 5363 are not in the logs, so the mechanism is inferred from the code and the timing, not checked against the data. The first check should be those three columns for 5363, and for 5284.
- The existing test `test_case_cost_stops_at_stable_time` in `tests/case_cost/test_case_cost_service.py` sets only `stable_at`. With one timestamp, `min` and `max` give the same result, so the test cannot catch this. No test covers a case with an escalation or closure after the stable time.
- The commit message says "latest status timestamp", but the commit body is empty. The intent may have been a different bug, so the author should confirm what they were trying to fix before the code is reverted or changed.

**Not part of this regression:** `cost-sync.log` also contains about 296 large decreases, starting 25 Aug, before any of the suspect deploys. These push costs down rather than up, so they don't match the complaint, but finance may want to look at them separately.

No code has been changed.

----- next turn -----

I fixed the cut-off and added a regression test. The fix is in place, but I have not committed it.

**The fix:** in `src/dispatch/case_cost/service.py` (line 353), `max(timestamps)` is back to `min(timestamps)`. The cut-off is now the earliest of `stable_at`, `escalated_at` and `closed_at`, which is what the function's comment already said.

**The regression test:** `test_case_cost_stops_at_earliest_stop_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets `stable_at` one hour ago and a later `escalated_at` or `closed_at`, then checks that only the hour up to `stable_at` is billed. Before the fix it failed with `7200.0 == 3600`, which reproduces the production symptom. It now passes.

**Test results** (`python -m pytest`, PostgreSQL running locally):
- `tests/case_cost`: 20 passed.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those three files on the original code. The same 8 fail there, so they predate this work and are not caused by it. I did not investigate them.

**Still open:**
- Existing case costs in the finance warehouse are wrong for the affected Stable cases (5284, 5327, 5264, 5363, 5406, and possibly others). The fix stops future syncs from inflating them, but it does not correct the rows already written. Finance will need to re-run the sync or restate those rows.
- I have not checked the fix against the database. The timestamps for case 5363 are still unverified.
- The commit `20f33137` message says "latest status timestamp", so the author may have been fixing a different problem. Confirm with them that nothing depended on the `max` behaviour before this ships.

----- next turn -----

The TypeError is fixed, and a cost is now produced for projects with missing values. Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` with no NULL check. Projects with a NULL in either field raise `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's hourly job catches the error per case, so the case gets no cost for that hour. The first occurrence is 8 Sep 15:55, and the log has 708 in total. The 6 Sep entries in the log are unrelated database connection failures.

**Fix:** a missing value falls back to the column default on the `Project` model (50000 and 2080), read from `Project.__table__`, so the model stays the only place those numbers live. The import is `from dispatch.project.models import Project`, and there is no circular import.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, and each one missing on its own.
- `test_calculate_case_response_cost_new_with_missing_project_values` checks that a case in such a project gets a cost instead of raising. Both tests failed before the fix.

**Results:** `tests/case_cost` passes (22 tests). The full suite has 362 passing and the same 8 failures as before in the AI, database and entity tests, which fail on the original code too. The new code passes `ruff check` and `ruff format`.

**Open items:**
- **Why the values became NULL is unknown.** No commit in the window touches project cost fields, and the logs have no project-level events. Someone should query the `project` table for rows where either field is NULL and check when they were changed.
- **`src/dispatch/incident_cost/service.py:133`** has the same unguarded division. I did not change it because it is outside the case cost job. It will hit the same error for incident costs if a project has NULL values.

----- next turn -----

## Recap

**Cost inflation (the first bug):** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For cases past New/Triage, the billing cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` rather than the earliest. A Stable case whose later timestamp came after the first stop kept accruing participant time. The first inflated case was 5284 on 3 Sep. Case 5363 (2,261 → 6,241 on 9 Sep) is the example from the report. The code now uses `min` again, and a regression test covers the case that failed before.

**Deploy:** `dispatch-web` rolled out `registry.example.com/dispatch:main-65f7df6e` on 2 Sep 2025 at 18:14Z. That image contains `20f33137`. The scheduler was redeployed with the same image at 18:15Z.

**Hourly TypeError (the second bug):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no NULL check. A NULL `annual_employee_cost` raised the TypeError, and the scheduler dropped that case's cost for the hour. The first occurrence was 8 Sep 15:55. The fix falls back to the `Project` model's column defaults (50000 and 2080) for either missing value. Both new tests failed before the fix.

**Open:**
- The 5363 timestamps have not been checked against the database.
- Why the project values became NULL is unknown. The logs have no project-level event, and no commit in the window touches them.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division and is not fixed.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```