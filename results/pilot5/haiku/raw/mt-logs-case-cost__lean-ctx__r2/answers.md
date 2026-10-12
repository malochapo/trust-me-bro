**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed one line in `src/dispatch/case_cost/service.py:353` from `min(timestamps)` to `max(timestamps)`. It shipped to production in the `main-65f7df6e` build, which is commit `65f7df6e` (the PR #6206 merge). That image rolled out to `dispatch-web` between 2025-09-02 18:14 and 18:15 UTC, and the old `main-3e0445ff` pods were gone by 18:15:54. `20f33137` is an ancestor of `65f7df6e` and not of `3e0445ff`, so this is the first production build with the change. No other case-cost or case-model code changed between the two builds.

**Mechanism:** `get_participant_role_time_seconds` caps a participant's billable time at a cut-off built from `stable_at`, `escalated_at`, and `closed_at`. With `min`, the cut-off is the first status change away from active work. With `max`, it is the last one. Escalated cases are frozen by design: the hourly job in `case_cost/scheduled.py` only recalculates `new`, `triage`, and `stable` cases, so an escalated case stops updating. A case that is escalated and then marked stable therefore gets billed for the whole span up to the stable time, including the time after escalation.

**Case 5363 fits this exactly:**
- Its classic cost rose by about 146 per hour until the Sep 5 16:20 sync, then stopped changing. That is consistent with escalation around then, though the logs have no status history to confirm it.
- It stayed at 2261 until Sep 9, when the stable transition triggered a recalculation. The sync at 12:20 wrote 6241, a jump of 3980 in one run.
- Under `min`, the cut-off would have stayed at the escalation time and the value would still be 2261. Under `max`, it moves to the stable time, which the 24-hour compression rule turns into about 43 effective hours (6241 / 145.5). That matches the jump.
- The other flagged cases (5284, 5327, 5264, 5406) are all Stable, and their jumps also began after the Sep 2 rollout.

**What I ruled out:**
- The cost-sync client upgrade to 1.5.0 on Sep 1 does not explain it. The sync copies the API's values, and the jump is in the value the API returned. I didn't inspect 1.5.0's code, since it isn't in this repo.
- The aggregate hourly diffs show no clean break, so the logs don't date the change more precisely than the per-case evidence above.

**Scope:** only five cases were flagged, because the warning fires above a threshold. Any case that went escalated → stable since Sep 2 18:15 is probably affected, and so is any escalated → closed case where the closed time is later than the escalation time. Those rows in `finance.case_response_cost` need to be found and corrected once the code is fixed.

**Not done:** I haven't changed any code. The likely fix is to revert line 353 to `min(timestamps)`, but I'd want the fix and the backfill reviewed first, since the warehouse rows since Sep 3 are wrong.

----- next turn -----

The fix is in, and the regression test fails on the old code and passes on the new code.

**Fix:** `src/dispatch/case_cost/service.py:353` now uses `min(timestamps)` again, so a participant's billable time stops at the first status change (escalation or stable, whichever comes first) rather than the last one.

**Regression test:** `test_case_cost_stops_at_first_status_change_after_escalation` in `tests/case_cost/test_case_cost_service.py`. It escalates a case one hour ago, marks it stable 30 minutes ago, and expects the participant's time to end at escalation (3600 s). The existing `test_case_cost_stops_at_stable_time` only sets `stable_at`, where `min` and `max` give the same result, which is why it never caught the bug.

**Verification (PostgreSQL running locally, `python -m pytest`):**
- Before the fix, the new test fails with `5400.0 == 3600`, which is the stable-time cut-off.
- After the fix, `tests/case_cost` passes (20 tests). `tests/case`, `tests/case_cost`, and `tests/case_cost_type` together pass (40 tests).
- I did not run the full test suite.

**Not done:**
- I haven't committed anything, since you didn't ask me to.
- The warehouse rows since Sep 3 are still wrong. Cases that were escalated and then marked stable need their costs recalculated, and I haven't identified them yet. Recalculation will not fix them on its own, because stable cases are recalculated only if their stored cost is older than `stable_at`.

----- next turn -----

The hourly case cost job's TypeError comes from projects whose `annual_employee_cost` or `business_year_hours` is NULL. It's fixed, and cases in those projects now get a cost using the model defaults.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `annual_employee_cost` by `business_year_hours` with no None check. The scheduler's traceback ends at that line. Both columns are nullable, and the model's `default=` only applies when a row is inserted without a value. An explicit NULL, which `ProjectUpdate` can write, is stored as-is. The per-case `except` in `case_cost/scheduled.py` logs the error and skips the case, so those cases never get a cost. I couldn't tell from the logs which project has the NULLs. A query on the project table would identify it.

**Fix:**
- `src/dispatch/project/models.py`: the defaults 50000 and 2080 are now `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and `ProjectBase` use them, so the values are defined once. Their values are unchanged, so there's no migration.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` replaces each missing value with its default separately. A project with only one value set keeps that value.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_model_defaults_for_missing_values`
- `test_get_hourly_rate_falls_back_for_each_missing_value`
- `test_calculate_case_response_cost_classic_with_missing_project_costs`, which covers the scheduler's path.

All three failed before the fix with the TypeError. They pass now, and `tests/case`, `tests/case_cost`, `tests/case_cost_type` and `tests/project` pass (49 tests).

**Full suite:** 363 pass, 8 fail. The failures are in `tests/ai/test_ai_service.py` (6, which need network access to download a tiktoken encoding), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those three files against a clean checkout of HEAD, with `PYTHONPATH` pointed at its `src`, and the same 8 fail there, so they were already failing before my changes.

**Not done:**
- `incident_cost/service.py:133` has the same `get_hourly_rate` code, so incident costs for those projects will fail the same way. I left it alone because you asked about the case job. It's a small follow-up if you want it.
- The logs also show a different case cost error on Sep 6 at 03:54. I didn't investigate it.
- Nothing is committed.

----- next turn -----

## Recap

**Cost bug.** In `get_participant_role_time_seconds`, commit `20f33137` changed the cost cut-off from `min` to `max` of the stable, escalated and closed timestamps. A case that was escalated and then marked stable kept accruing participant time until the stable time, although the escalated-case recalculation had frozen its cost at escalation. Case 5363 went from $2,261 to $6,241 that way. The fix restores `min`, and `test_case_cost_stops_at_first_status_change_after_escalation` covers it. The test fails on the old code and passes on the fix.

**Deploy.** The `main-65f7df6e` image (commit `65f7df6e`) was rolled out to `dispatch-web` between 2025-09-02 18:14 and 18:15 UTC. The first commit that contains `20f33137` is in that build. The earlier `main-3e0445ff` build does not contain it.

**First inflated case.** The first flagged inflated cost is case 5284, on 2025-09-03. The flags only cover cases over the warning threshold, so an earlier inflated case that wasn't flagged would not show up in these logs.

**Hourly TypeError.** It occurs when a project's `annual_employee_cost` is NULL. The traceback's left operand is `NoneType`. Each affected case is logged and skipped, so it gets no cost. `get_hourly_rate` now falls back to the project model defaults (50000 and 2080), and there are three new tests for it. Two of them failed on the old code. The `incident_cost` service has the same code and is not fixed. Eight unrelated tests fail on clean HEAD too, six of them because the test environment has no network access.

**Not done.** Nothing is committed. The cases whose costs were inflated still need recalculation in the warehouse, and the incident-cost helper needs the same NULL handling.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost