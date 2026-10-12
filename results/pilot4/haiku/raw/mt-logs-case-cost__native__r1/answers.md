**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. The cut-off is built from `stable_at`, `escalated_at` and `closed_at`. The function's own comment still says it wants "the earliest relevant timestamp". With `max`, a case that was escalated and later marked stable is charged for every participant-hour between the escalation and the stable mark. Those hours should not be billed.

**Deploy that shipped it:** `65f7df6e` (which contains `20f33137`, verified by ancestry). The `dispatch-web` and `dispatch-scheduler` pods rolled to `main-65f7df6e` on 2025-09-02 at 18:14–18:15 UTC, after the `dispatch-db-upgrade-65f7df6e` job at 18:14:09. The previous production image was `main-3e0445ff`.

**Evidence that it matches the data:**
- The first flagged jump is on Sep 3 at 11:20 (case 5284, 3331 → 8804), after the Sep 2 deploy. The later flags are cases 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12). All are Stable cases, and nothing flagged before Sep 3.
- Case 5363 is flat at 2261 from Sep 5 16:20 to Sep 9 11:20, then jumps to 6241 in the Sep 9 12:20 run. That is when it was marked stable, and it fits a cut-off moving from an earlier escalation to the later stable time. The logs have no case status history, so the escalation date is inferred from the flat line, not confirmed.
- The `20f33137` diff is the only change to this logic since `200cd428` (June 2025, which added the stable status).

**Ruled out:**
- The finance job `case-cost-sync` went to 1.5.0 on Sep 1 at 10:20. It ran cleanly on Sep 1–2 with no flags, and the spikes start only after the Dispatch deploy.
- Deploy `51546e13` on Sep 4 came after the first spike on Sep 3, so it did not cause the jump, though it's still in production.
- `scheduler.log` has no case-level cost information, so it did not help locate the cause.

**Why the tests did not catch it:** `tests/case_cost/test_case_cost_service.py::test_case_cost_stops_at_stable_time` sets only `stable_at`, so `min` and `max` give the same answer. No test covers escalation followed by stable, which is the case that breaks.

**Intent:** the commit message says "latest" on purpose, so the author chose it. The code comment, the variable name and the billing rule all point to earliest, so I think the change is wrong, but that call is yours.

**Suggested fix (not applied):** revert to `min(timestamps)`, add a test where `escalated_at` comes before `stable_at` and the cost stops at the escalation, and then re-run the sync to correct the affected cases (5284, 5327, 5264, 5363, 5406 and any others flagged since Sep 2). I have not run the test suite and made no code changes.

----- next turn -----

The fix is in and the regression test is added. All 20 case-cost tests pass with `python -m pytest`.

**Changes**
- `src/dispatch/case_cost/service.py:353`: reverted `max(timestamps)` to `min(timestamps)`. The cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, which matches the function's comment.
- `tests/case_cost/test_case_cost_service.py`: added `test_case_cost_stops_at_first_status_change`. It escalates a case three hours ago, marks it stable one hour ago, and expects the participant's time to stop at the escalation (one hour from assumed-at, not three).

**Verification**
- With `max` restored, the new test fails. With `min`, it passes. So it would have caught the regression.
- I didn't run the full test suite, only `tests/case_cost`.

**Not done**
- I didn't re-run `case-cost-sync` or correct the warehouse rows for the affected cases (5284, 5327, 5264, 5363, 5406, and any others flagged since Sep 2). That needs a decision from finance on whether to backfill, and it touches production data.
- The fix is not deployed. It goes live with the next Dispatch release, and the warehouse values stay wrong until they're corrected.

----- next turn -----

The `TypeError` is fixed, and the case-cost tests pass (22 of 22, including two new ones).

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. For some projects one of those columns is `NULL`, which raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The error is caught per case, so only those cases are dropped, but every hourly run hits them again. The log has 708 of these, all from `case_cost`, the first on Sep 8 at 15:55.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults use them, so the values are unchanged.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants when a value is `None`. It checks for `None` rather than falsiness, so a real `0` is not replaced.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_when_unset` checks the rate is 25 (50000 / 2080, rounded up).
- `test_case_cost_calculated_when_project_values_unset` checks the classic cost for two hours is 50 with both values unset, and that the new model calculates without raising.
- Both fail on the old code and pass with the fix. I restored the fixed file after that check.

**Not changed:**
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` with no fallback. The incident job's logs show no `TypeError`, so I left it alone. It will fail the same way for any incident whose project has these values unset.
- `src/dispatch/individual/service.py:104` already hard-codes the same 50000 and 2080 fallbacks. I didn't switch it to the new constants.
- Projects with these values unset are not backfilled. The fallback only covers the calculation.

----- next turn -----

The recap is below. The fix is in the working tree and not committed or deployed, and the warehouse values are not corrected yet.

**Summary**

- **Inflated case costs (cost bug):** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off is built from `stable_at`, `escalated_at` and `closed_at`, and the function's comment says it should be the earliest. With `max`, a case that was escalated and later marked stable was billed for the time between those two events. The change shipped in `main-65f7df6e`, which went live on 2025-09-02 at 18:14 UTC. The first inflated cost was case 5284 on 2025-09-03. Later flagged cases were 5327, 5264, 5363 and 5406.
- **Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. Projects with `annual_employee_cost` unset raised the error on every hourly run from 2025-09-08 onward, 708 times in total. The fix uses the project model's defaults (50000 and 2080) for missing values.
- **Fixes in the working tree (uncommitted):**
  - `src/dispatch/case_cost/service.py`: `min` restored, and `get_hourly_rate` falls back to defaults.
  - `src/dispatch/project/models.py`: defaults are named constants.
  - `tests/case_cost/test_case_cost_service.py`: three new regression tests. Each fails on the old code and passes with the fix. All 22 case-cost tests pass.

**Open items**

- Warehouse rows for the flagged cases still show inflated values. Finance needs to decide on a backfill.
- `incident_cost` has the same `get_hourly_rate` with no fallback. Its logs show no TypeError, but projects with these values unset would fail there too.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```