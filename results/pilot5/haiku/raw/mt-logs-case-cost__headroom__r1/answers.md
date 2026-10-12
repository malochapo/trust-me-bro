**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, authored 2025-09-02 09:29 PDT) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

For cases that are not new or triage, the function picks a cut-off from `stable_at`, `escalated_at` and `closed_at`. The comment directly above the code says it should be "the earliest relevant timestamp for cost calculation cut-off", so `min` was the intended behaviour. With `max`, the cut-off moves to the latest of those timestamps, so each participant accrues time for longer and the case cost goes up. The commit title says "latest", but the cost model's comment and the surrounding logic both expect the earliest.

**Deploy that shipped it:** the first production rollout containing the commit is `dispatch:main-65f7df6e`, which the cluster events show rolling out to `dispatch-web` and `dispatch-scheduler` at **2025-09-02 18:14–18:15Z**. Its database upgrade job ran at 18:14:09Z. `main-51546e13` (2025-09-04 16:52Z) also contains the commit, but the anomalies began before it.

**Timing against the logs:**
- The first flagged spike is case 5284 at **2025-09-03 11:20Z**, the first sync after the 9/2 deploy. Nothing in the cost-sync warnings before that is a comparable jump; the earlier warning on 8/31 is a connection timeout.
- Case 5363 shows the steady climb after its first sync on 9/4 (about +145 per hour, from 131 to 3425 by 9/5 08:20Z). It drops to 1243 at 9/5 09:20Z, then climbs again to 2261. The 9/9 12:20Z sync shows the jump to 6241 you reported, flagged as Stable.
- Other flagged cases follow the same pattern: 5327 (9/5), 5264 (9/8, 3285 → 11987), 5406 (9/12).

**What I could not confirm:**
- The logs don't include `stable_at`, `escalated_at` or `closed_at` for case 5363, so I can't show that a later escalation or closure timestamp moved the cut-off on 9/9. That is the most likely reason the jump happened on 9/9 and not earlier, but it is inferred from the code, not from data.
- I didn't find an explanation for the 9/5 09:20Z drop from 3425 to 1243 in these logs.

No code has been changed. The fix is most likely to revert `max` to `min` on that line, but please confirm the intended cut-off semantics with whoever wrote the commit before shipping it. Once case 5363's timestamps are available, a restored `min` should reproduce the pre-9/2 values.

----- next turn -----

I reverted the cost cut-off to `min` and added a regression test. The test fails when the bug is reintroduced and passes with the fix.

**Fix:** `src/dispatch/case_cost/service.py:353` now uses `min(timestamps)` instead of `max(timestamps)`. The diff is that one line. This restores the behaviour the function's comment describes: the cost stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.

**Regression test:** `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets `stable_at` one hour ago and `closed_at` now, then expects the participant's time to stop at `stable_at`. The existing tests set only `stable_at`, so `min` and `max` give the same result and they never caught the change. The new test covers the case where a second timestamp comes later.

**Verification:**
- `python -m pytest tests/case_cost/test_case_cost_service.py`: 20 passed with the fix.
- With `max` put back temporarily, the new test failed. I then restored `min`.
- `python -m pytest tests/case_cost tests/case_cost_type tests/participant_role`: 29 passed.
- `ruff` is not installed in this environment, so I did not run lint or format checks.

Nothing is committed. The cost figures already in the warehouse are not corrected by this change. Those would need a recalculation through the finance team's sync, which I have not run.

----- next turn -----

The hourly cost job crashed because some projects have NULL `annual_employee_cost` or `business_year_hours`, and `get_hourly_rate` divided by them without a check. It now falls back to the project model's defaults, and the new tests fail on the old code.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computed `annual_employee_cost / business_year_hours` directly. The scheduler log shows 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` entries, the first at 2025-09-08 15:55. The model defaults (50000 and 2080) are SQLAlchemy `default=` values, which apply only when a row is inserted. Projects that already have NULL in those columns never pick them up.

**Fix:**
- `src/dispatch/project/models.py`: the two defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`, used by the column definitions.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants when a value is missing.

I used `or`, so a stored 0 also counts as missing. That avoids a divide-by-zero for hours, but it means a project that explicitly sets cost to 0 gets the default instead. Say if you want `is None` checks.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_defaults_for_unset_project_values` covers each value missing alone, then both.
- `test_calculate_case_response_cost_project_without_cost_settings` runs the cost calculation for a project with both values unset.

With the old logic restored, both fail. With the fix, `python -m pytest tests/case_cost` passes (22 tests), and `tests/case_cost`, `tests/project` and `tests/incident_cost` pass together (43 tests).

**Not done:**
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` without the fallback. The incident cost job would hit the same TypeError for a project with NULL values. I left it alone because you scoped this to the case cost job. It's a one-line-equivalent change if you want it.
- The logs don't name the affected projects, so I haven't confirmed which projects have NULLs in production. The fix only changes behaviour for NULL values.
- The traceback paths are in the installed package, not this checkout. I assumed the deployed code matches this repo, which I did not verify.

Nothing is committed.

----- next turn -----

## Recap

**Incident:** Since 2025-09-02, case response costs in the finance warehouse have been inflated for some cases. Cases that were marked stable got a cost several times their correct value. Separately, since 2025-09-08 the hourly case cost job has logged a TypeError for some projects.

**Cost inflation (root cause):**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds`, from `min(timestamps)` to `max(timestamps)`.
- The function picks the cost cut-off from `stable_at`, `escalated_at` and `closed_at`. Its comment says the earliest of these should be used. With `max`, the cut-off moved to the latest of them, so participants kept accruing time after the case was stable.
- The first production rollout containing the commit was `main-65f7df6e`, at 2025-09-02 18:14Z.
- The first inflated sync was 2025-09-03 11:20Z (case 5284, 3331 → 8804). Other flagged cases followed: 5327, 5264, 5363 (the 9/9 case you reported) and 5406.
- Existing tests set only `stable_at`, so `min` and `max` gave the same result and the tests passed.

**Hourly TypeError:**
- `get_hourly_rate` in `src/dispatch/case_cost/service.py` computed `annual_employee_cost / business_year_hours` with no check. The log shows 708 TypeErrors from 2025-09-08 15:55 onward.
- The message `'NoneType' and 'int'` means `annual_employee_cost` was NULL. The model defaults (50000 and 2080) are insert-time defaults, so projects that already had NULL values never received them.

**Fixes (not committed):**
- `get_participant_role_time_seconds` uses `min` again.
- The model defaults are named constants in `src/dispatch/project/models.py`. `get_hourly_rate` falls back to them when a value is unset (`or`, so a stored 0 also counts as unset).

**Tests:**
- `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp` covers the cut-off. It fails with `max` and passes with `min`.
- `test_get_hourly_rate_uses_defaults_for_unset_project_values` and `test_calculate_case_response_cost_project_without_cost_settings` cover the fallback. Both fail on the old code.
- `tests/case_cost`, `tests/case_cost_type`, `tests/participant_role`, `tests/project` and `tests/incident_cost` all pass with the fixes.

**Open items:**
- The same unguarded `get_hourly_rate` exists in `src/dispatch/incident_cost/service.py:131`. The incident cost job would hit the same TypeError for NULL projects. I haven't changed it.
- The cost values already in the warehouse are not corrected. That needs a recalculation through the finance sync, which I have not run.
- The logs don't name the affected projects, so I haven't checked which production projects have NULLs.
- The traceback paths are from the installed package. I assumed it matches this checkout.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```