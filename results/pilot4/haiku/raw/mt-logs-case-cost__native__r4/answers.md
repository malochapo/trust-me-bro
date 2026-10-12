## Root cause

Commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `src/dispatch/case_cost/service.py:353`:

```python
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. Participant time is cut off at the earliest of these, so cost stops when the case first stops being active work. With `max`, the cut-off moves to the latest of them. Cost then keeps accruing from escalation until the case is stabilized or closed.

The code and its comments show the `min` was intended. Line 332 says "earliest relevant timestamp", line 363 says "the role's renounced_at … if it happened before the case was marked as stable or closed", and `200cd428` (which added stable status) introduced `min`. The commit title says "latest", which contradicts the code comment. I'd confirm the intent with Jordan before reverting.

## Deploy that shipped it

- `main-65f7df6e` is the first production image that contains `20f33137`. It was rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 18:14–18:15 UTC** (events.log, `dispatch-db-upgrade-65f7df6e` followed by `dispatch-web-zrhzjwmzrh` and `dispatch-scheduler-qdd74fpnsl`).
- Later images `main-51546e13` (Sep 4 16:52 UTC) also contain the change, so the bug is still live.
- The finance cost-sync job moved to 1.5.0 on Sep 1. That is not the cause: cost-sync only copies values the Dispatch API returns, and the large jumps don't start until after the Sep 2 deploy.

## Evidence

- In cost-sync.log, the per-run deltas are normal, with no jumps before Sep 3. Across Aug 25–Sep 14 there are only five single-run jumps over 400, on Sep 3, 5, 8, 9 and 12 (cases 5284, 5327, 5264, 5363, 5406). Each is a case that went escalated and then stable, and the jumps are roughly 1.7× to 3.6× the prior cost.
- Case 5363 shows the pattern clearly. Its classic cost grew about 146 per hour and then stopped changing from Sep 5 16:20 to Sep 9 12:20. That is consistent with a cut-off at its escalation time. At Sep 9 12:20, when it was marked stable, the cost jumped from 2261 to 6241 in one run and then stopped changing. I didn't verify the escalation time directly, since the logs don't include case data.
- The existing test (`tests/case_cost/test_case_cost_service.py:357`) only sets `stable_at`, so it can't detect the `min`/`max` difference. It passes with the regression.

## Suggested next steps (no changes made)

1. Confirm the intended cut-off with Jordan Lee, then revert line 353 to `min` (or fix the title and comment if `max` was really wanted).
2. Add a test where `escalated_at` precedes `stable_at`, to lock in the earliest-timestamp behaviour.
3. Have finance recompute the affected cases (at least 5264, 5284, 5327, 5363, 5406, plus any that were escalated and later stabilized or closed since Sep 2).

----- next turn -----

I reverted the cut-off to `min`, added a regression test, and checked that the test fails against the buggy code. The change is not committed.

**The fix** (`src/dispatch/case_cost/service.py:353`): `max(timestamps)` is back to `min(timestamps)`, so participant time stops at the earliest of `stable_at`, `escalated_at` and `closed_at`, as the code comments describe.

**The regression test** (`tests/case_cost/test_case_cost_service.py`, `test_case_cost_stops_at_first_status_timestamp`): the existing stable-time test only sets `stable_at`, so it couldn't tell `min` from `max`. The new test escalates a case two hours ago, marks it stable one hour ago, and asserts that participant time stops at escalation, one hour after assignment rather than two.

**Verification:**
- With `max` restored, the new test fails (expected 3600 seconds, got 7200 in the regressed version). With `min` it passes.
- `tests/case_cost/test_case_cost_service.py`: 20 passed.
- Full suite with `python -m pytest`: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail with my changes stashed, so they predate this fix. I didn't investigate them.

**Still open:**
- Commit `20f33137`'s title says "latest status timestamp", which contradicts the code comments. I reverted to `min` because the comments and the original design both say earliest. If Jordan Lee wanted `max` for a different reason, the new test would need to change too.
- Costs already in the warehouse are still overstated for affected cases (5264, 5284, 5327, 5363, 5406, and any escalated-then-stabilized or closed case since Sep 2). The fix doesn't correct those rows; finance will need to recompute them after the deploy.

----- next turn -----

The hourly TypeError is fixed. Cases on projects with a `NULL` annual employee cost or business year hours now get a cost, using the project model's defaults.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns have Python defaults (50000 and 2080), but those only apply when a row is inserted. A project whose columns were saved as `NULL` reaches the division as `None`, so the case-cost job logs `unsupported operand type(s) for /: 'NoneType' and 'int'` and skips that case. The scheduler log has 708 of these errors, all from `dispatch.case_cost.scheduled`, starting Sep 8.

**Changes:**
- `src/dispatch/project/models.py`: the two defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults use them, so nothing else changes.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes the constant for each `None` value before dividing.
- `tests/case_cost/test_case_cost_service.py`: a parametrized `test_get_hourly_rate` covers both values set, cost missing, hours missing, and both missing. With the original code the three missing-value cases fail with the TypeError; with the fix all four pass.

**Verification:** the case cost tests pass (24 passed). The full suite gives 364 passed, 4 skipped, 8 failed. The 8 are the same unrelated failures as before (AI service, restricted case filter, entity service), which also fail on the untouched tree.

**Not done:**
- `incident_cost/service.py:133` has the same division with no `None` handling. It isn't logging errors in these logs, but it would fail the same way for a project with a `NULL` value. I left it alone because you asked about case costs; say if you want it fixed too.
- I didn't check the database for which projects have `NULL` values, since I only have the logs and the test database.
- Nothing is committed.

Separately, a background test run from earlier was still holding the test database and caused a burst of "database is being accessed" errors on one attempt. I stopped that process and reran; the numbers above are from the clean run.

----- next turn -----

I checked each case's post-deploy deltas against its own normal rate. The earliest real step is case 5284 on Sep 3 at 11:20 UTC. The Sep 2 19:20 value is within normal noise, so I'm using Sep 3 as the first inflated date.

## Recap

**Inflated costs (the cut-off bug):** Commit `20f33137` changed the participant-time cut-off in `get_participant_role_time_seconds` from `min(...)` to `max(...)`. Time was then counted from escalation until stabilization or closure instead of stopping at the first status change. That produced step increases when escalated cases were marked stable or closed (5284, 5327, 5264, 5363, 5406). It shipped in image `main-65f7df6e`, rolled out to production on 2025-09-02 at 18:14–18:15 UTC. The fix restores `min(...)`, and a new test fails on `max` and passes on `min`.

**Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with a `NULL` value for these settings hit `None / int`, so the case-cost job skipped those cases each hour from Sep 8. The fix falls back to the project model's defaults (50000 and 2080), and new parametrized tests cover each missing-value case.

**Not covered by this fix:** `incident_cost/service.py` has the same division without a fallback. It isn't logging errors, but it would fail the same way for a project with a `NULL` value.

**Still open:** Nothing is committed yet. Warehouse rows for the affected cases still need recomputing after the fix ships. The eight failing tests in AI, restricted case filter and entity search predate this work.

The six fields for the report:

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost