## Root cause

Commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `src/dispatch/case_cost/service.py`, in `get_participant_role_time_seconds`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. Those timestamps are the cost cut-off, and the function's own comment still says the cut-off should be the **earliest** of them (`# Determine the earliest relevant timestamp for cost calculation cut-off`). With `max`, a case that was escalated and later marked Stable is billed until the Stable mark, not until the escalation. Its participants' time windows get longer, so the cost multiplies. The commit title and the code agree with each other, but both contradict the comment and the renounce logic below it, which says to cut off at the point the case "was marked as stable or closed".

The damage is limited to cases that have more than one of these timestamps, which is why only some Stable cases jump. The cost-sync log shows the jumps are all Stable cases with about 2.5–3.7× increases:

| Date (UTC) | Case | Classic cost change |
|---|---|---|
| Sep 3 11:20 | 5284 | 3331 → 8804 |
| Sep 5 16:20 | 5327 | 2244 → 5539 |
| Sep 8 10:20 | 5264 | 3285 → 11987 |
| Sep 9 12:20 | 5363 | 2261 → 6241 |
| Sep 12 11:20 | 5406 | 1975 → 4945 |

The hourly growth of about +146 for case 5363 on Sep 4 (131 → 277 → 422) is expected accrual for an open case, where the cut-off is "now". It is not the bug.

## The deploy

- `20f33137` is an ancestor of `65f7df6e` ("feat(ui): allow filtering by dedicated channel cases (#6206)"). Its own image tag never appears in `events.log`.
- `main-65f7df6e` was rolled out to production on **Sep 2 at 18:14Z**: the `dispatch-db-upgrade-65f7df6e` job, then `dispatch-web` and `dispatch-scheduler`. This is the first image that contains the change, and it is the deploy that shipped it.
- The first flagged case is Sep 3 11:20, the first sync after that rollout in which a Stable case showed the jump.
- Ruled out: `main-51546e13` (rolled out Sep 4 16:52Z) came after the anomaly began, so it did not introduce it. The `main-3e0445ff` rollout on Aug 27 predates the change.

## Notes

- The same function is used by the other cost path in `case_cost/service.py`, so the bad values affect the classic model as reported, and possibly the new model too. I did not check the new-model path in detail.
- `tests/case_cost/test_case_cost_service.py` has a `test_get_participant_role_time_seconds` test, but I did not check whether it covers the multi-timestamp case. I also did not run the test suite.
- No code has been changed. The likely fix is to revert to `min`, which matches the comment, then add a test with an escalated-then-stable case. Tell me if you want that done.

----- next turn -----

The cost-cut-off bug is fixed and covered by a regression test. The change is uncommitted in the working tree.

**Fix:** `src/dispatch/case_cost/service.py:353` now uses `min(timestamps)` instead of `max(timestamps)`. That returns the earliest of `escalated_at`, `stable_at` and `closed_at`, which is what the function's comment already says it should do.

**Regression test:** `tests/case_cost/test_case_cost_service.py::test_case_cost_stops_at_earliest_status_timestamp`. The case is escalated 1.5h ago, marked stable 1h ago, and closed 30 minutes ago. The participant has been assigned for 2h. The test expects the cost window to end at the escalation, which is 1800s.

The existing `test_case_cost_stops_at_stable_time` only sets `stable_at`, so it never had a case with more than one status timestamp. That is why the suite passed with the bug in place.

**Verification:**
- Before the fix, the new test failed with `5400 == 1800`, which is the inflated window from the bug.
- After the fix, `python -m pytest tests/case_cost -q` passes: 20 passed.

I did not run the full test suite, and I did not commit. Tell me if you want the commit made.

----- next turn -----

Cases in projects with a missing cost setting now get a cost instead of raising `TypeError`. The fix and tests are in the working tree and uncommitted.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `project.annual_employee_cost / project.business_year_hours`. When either value is `NULL` in the database, that raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's `calculate_cases_response_cost` catches the exception per case, so those cases are skipped each hour. The log has 708 of these, all from this line.

**Fix:** When either value is `None`, `get_hourly_rate` uses the default from the `Project` model's column definition (currently 50000 and 2080). I read the defaults from `Project.__table__`, so they are not duplicated. I also added the `Project` import to the module.

**Tests:** Four new tests in `tests/case_cost/test_case_cost_service.py`:
- Project values set: the rate is computed from them.
- Missing annual employee cost: the default is used.
- Missing business year hours: the default is used.
- A full classic cost calculation on a project with both values missing now returns a positive cost.

`python -m pytest tests/case_cost` passes, 24 tests. Against the original `get_hourly_rate`, the three tests for missing values fail with the same `TypeError`.

**Not covered:**
- `src/dispatch/incident_cost/service.py:133` has the same `get_hourly_rate` and the same crash for incidents. I left it alone because you scoped this to the case cost job. It is a two-line change if you want it.
- I did not check what set these projects' values to null on or around September 8, or whether the cause is a bad migration or a settings change.
- The `min` fix from the previous step is still in place.

----- next turn -----

I have what I need. Recap of the incident:

**Cost bug (`case_cost`):** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `escalated_at`, `stable_at` and `closed_at`, not the earliest, which the function's comment says it should be. Any case with more than one of these timestamps was billed too long, and those cases showed jumps of 2.5–3.7×. The commit reached production in `main-65f7df6e`, rolled out on Sep 2 at 18:14Z. The first inflated case I found is case 5284 on Sep 3 at 11:20Z. The cost-sync job only flags Stable cases, so an escalated or closed case inflated earlier would not show up in the warnings. I checked the classic-cost diffs since the deploy for jumps above 1.5× on cases with a base over 500, and found no earlier ones.

**Hourly TypeError (`scheduler`):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. The log error reads `'NoneType' and 'int'`, so the missing value is `annual_employee_cost`. Those cases were skipped every hour. The fix uses the `Project` column defaults when either value is missing.

**Fixes and tests:** The `min` fix has a regression test that fails on the old code. The hourly-rate fallback has four tests, three of which fail on the old code. The case cost suite passes: 24 tests.

**Not fixed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded `get_hourly_rate`. The `max` bug in the case cost code is not in the incident cost code, which I did not check in depth.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```