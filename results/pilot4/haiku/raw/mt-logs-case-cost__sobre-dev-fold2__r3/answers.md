**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` (~line 353):

```python
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

`timestamps` holds whichever of `stable_at`, `escalated_at` and `closed_at` are set. The cost for each participant role runs from `assumed_at` to a cut-off, and that cut-off is now the latest of those timestamps rather than the earliest. For a case that was escalated before it was marked stable, the billed window now runs to the stable mark instead of stopping at the escalation. For a stable case that later closes, it runs to the close. Hourly rates and cost models are untouched, which fits what finance sees.

**Deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14 UTC** (events.log). `65f7df6e` is a descendant of `20f33137`, and the previous image, `main-3e0445ff`, does not contain it. The same commit also went out in `main-51546e13` on 09-04. That image is current production, so the bug is still live.

**Timeline evidence:**
- cost-sync reports no flags and no warnings from 08-25 through 09-02, and its daily change ratios are normal.
- The first flag is 2025-09-03 11:20. Later flags: 09-05, 09-08, 09-09 (case 5363, 2261 → 6241), and 09-12.

**Ruled out:**
- The cost-sync bump to 1.5.0 on 09-01 is not the cause. Its run logs show no change in behaviour, and the anomalies start after the 09-02 deploy.
- The scheduler log has no case-cost errors that change at the deploy.

**Why tests missed it:** `tests/case_cost/test_case_cost_service.py` only sets `stable_at`, so `min` and `max` give the same result. Nothing covers a case with two or more of the three timestamps set.

**Open question for you:** the commit message says "latest status timestamp", but the function's own comment says "Determine the earliest relevant timestamp for cost calculation cut-off", and the test is named `test_case_cost_stops_at_stable_time`. That contradicts the intent. The fix direction depends on which behaviour finance expects, so it's worth confirming with Jordan Lee or the finance team before changing it.

**Limits:** I haven't checked case 5363's timestamps directly because there's no database access here. The mechanism fits the reported jump (escalated earlier, marked stable 09-09), but that's inference from the code, not a reproduction. No code has been changed.

----- next turn -----

I reverted the cut-off to the earliest timestamp and added a regression test. The new test fails on the old code and passes with the fix. The case-cost and related case test directories pass (49 tests, plus the full 20 in `tests/case_cost`).

**Changes:**
- `src/dispatch/case_cost/service.py`: `max(timestamps)` back to `min(timestamps)`. This matches the function's comment ("earliest relevant timestamp") and the `test_case_cost_stops_at_stable_time` behaviour.
- `tests/case_cost/test_case_cost_service.py`: new `test_case_cost_cut_off_is_earliest_timestamp`. It sets up a case escalated two hours ago and then marked stable one hour ago, and asserts the participant time equals the escalation-only case (3600s). On the current code it returns 7200s, so it fails.

I didn't commit anything.

**Decision for you:** I took the commit title's "latest" as the mistake, because the code comment, the stable-time test, and the pre-09-02 finance numbers all point to "earliest". If Jordan Lee intended "latest" for a reason, this needs a conversation with finance first. Finance will also need to correct the affected rows. The flagged cases (5284, 5327, 5264, 5363, 5406) are only the ones that crossed the warning threshold, so the full set should be recomputed from the cutover on 2025-09-02.

----- next turn -----

The hourly case-cost job was failing because `get_hourly_rate` divided by NULL values. I fixed it and added a test. The case-related test directories pass (65 tests, including the incident-cost tests), and the new test reproduces the scheduler's TypeError on the old code.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours`. Some projects have NULL in one or both columns. The model's `default=50000` / `default=2080` only apply on insert, and the cost path never handled NULL. The TypeError is `unsupported operand type(s) for /: 'NoneType' and 'int'`. I found 708 occurrences in `scheduler.log`. The sampled ones are from 2025-09-08 onward, but I didn't check for earlier ones or identify the affected projects.

**Fix:** a missing value now falls back to the project model defaults, 50000 and 2080. I used explicit `is not None` checks, so a real value of 0 is not replaced. Each fallback is applied separately, so a project with only one value missing uses that value and the default for the other.

**Test:** `test_get_hourly_rate_falls_back_to_project_model_defaults` in `tests/case_cost/test_case_cost_service.py` covers NULL for both fields, NULL for only the hours, and NULL for only the cost. It failed on the old code with the same TypeError.

**Notes:**
- The fallback values are hard-coded, as `src/dispatch/individual/service.py` already does, rather than read from the model's column defaults. Say if you'd rather have a shared constant.
- `incident_cost/service.py:133` has the same unguarded division. I didn't change it because it's outside the case-cost job, but it will fail the same way for a project with NULL values.
- Ruff reformatted the two files. Also, my earlier fix in `get_participant_role_time_seconds` (`max` → `min`) is still in place. Nothing is committed.

----- next turn -----

The earlier ratio check is noisy, and large jumps also appear before the deploy, so it can't date the first inflated cost precisely. I'll use the earliest inflation I could tie to the bug (the 2025-09-03 flag) and note the caveat.

## Incident recap

**Symptom:** Since early September, the finance warehouse received case response costs several times higher than the previous hour, for Stable cases with no rate or model change. Example: `dispatch-default-security-5363` went from $2,261 to $6,241 on 2025-09-09. Separately, the scheduler's hourly case-cost job logged a TypeError for some cases from 2025-09-08.

**Root cause 1 (inflated costs):** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off for a case's participant time is now the latest of stable, escalated and closed rather than the earliest. Cases that were escalated and later marked stable accrued cost up to the stable mark. The function's own comment and the existing stable-time test both describe the earliest-timestamp behaviour. Shipped in `registry.example.com/dispatch:main-65f7df6e`, rolled out 2025-09-02 18:14 UTC; still live via `main-51546e13` (2025-09-04). Fixed by reverting to `min`, with a regression test that fails on the old code.

**Root cause 2 (TypeError):** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Projects with NULL in either column (the model defaults apply only on insert) raised TypeError, so those cases got no cost. Fixed by falling back to the model defaults (50000 and 2080), with a regression test.

**Caveats for the report:**
- The first inflated cost is not conclusively dated. The earliest flagged inflation is 2025-09-03; large jumps also appear before the deploy, so I can't attribute them to the bug.
- Affected finance rows need recomputing from 2025-09-02 for the inflation bug. The TypeError cases also need recomputing, but I didn't identify which projects they were.
- `incident_cost/service.py:133` has the same unguarded division and is not fixed.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours (project-level NULL; the TypeError is raised by get_hourly_rate, which uses both)