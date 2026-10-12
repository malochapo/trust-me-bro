**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `src/dispatch/case_cost/service.py:353` in `get_participant_role_time_seconds`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

For cases that are not new or in triage, the cost cut-off is now the latest of `stable_at`, `escalated_at` and `closed_at`, instead of the earliest. A case usually escalates before it becomes stable, so the cut-off moves from `escalated_at` to `stable_at`. Every participant's billable time then includes the whole escalated-to-stable window, which is where the multiplier comes from. The commit message says "latest", so the change looks deliberate, but it reverses the cut-off that the stable-status feature (`200cd428`, June 2025) was built on.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14 UTC. `events.log` shows the `dispatch-db-upgrade`, `dispatch-web` and `dispatch-scheduler` pods pulling it, and `scheduler.log` shows `Starting scheduler...` at 18:15:30 on that date. The commit is an ancestor of `65f7df6e` and is still on `main`. The previous deploy (`main-3e0445ff`, 2025-08-27) predates it, and `main-51546e13` (2025-09-04) does not revert it.

**Evidence that fits the timeline:**
- The first flagged Stable case in `cost-sync.log` is on 2025-09-03, the next day after the rollout. Later flags are on 09-05, 09-08, 09-09 and 09-12.
- The commit is the only change to the cost calculation in the rollout range. `42699ebc` also changed `database/service.py`, but it only flattens a query filter and does not touch the cost math.
- The existing tests (`tests/case_cost/test_case_cost_service.py`) set one timestamp at a time, so they would not catch the change.

**Caveats:**
- I have not confirmed the exact per-case numbers. The logs do not contain `stable_at`, `escalated_at` or `closed_at` for case 5363, so I cannot show that its escalation-to-stable gap accounts for the 2261 → 6241 jump.
- Case 5363 still accrues about 145 per hour while it is Stable (Sep 4 to Sep 5), which a frozen cut-off should prevent. Its drop from 3425 to 1243 on Sep 5 is also unexplained. Both need the case row and its participant roles from the database to resolve.
- Large per-run jumps show up throughout the whole window, so the 2× ratio alone does not isolate the change. The discriminator is the Stable-case jumps after the 09-02 restart.

**Suggested next step (not done, since you asked for no code changes):** check the 5363 row (`status`, `escalated_at`, `stable_at`, `closed_at`) to confirm the escalation-to-stable gap. Then revert to `min` on `main`, or define the cut-off explicitly as `stable_at` for stable cases. Add a test with both `escalated_at` and `stable_at` set. Finance will need a backfill for the affected cases, because the hourly job only upserts rows that changed.

I made no changes to the repository.

----- next turn -----

I reverted the regression in `src/dispatch/case_cost/service.py` and added a test that fails on the broken code and passes on the fix.

**The fix:** line 353, `participant_role_renounced_at = max(timestamps)` is back to `min(timestamps)`. That restores the cut-off the code used before `20f33137`: the earliest of escalated, stable and closed.

**The regression test:** `test_get_participant_role_time_seconds_uses_earliest_closing_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets up a closed case that was escalated 3h ago, marked stable 2h ago and closed 1h ago, with the participant assigned 4h ago. The expected time in role is 1 hour, which ends at escalation.
- On the broken code it fails: `assert 10800.0 == 3600`.
- On the fix it passes.

**Test results** (`python -m pytest`, PostgreSQL local):
- `tests/case_cost`: 20 passed, including the new test.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those same test files with my changes stashed and got the same 8 failures, so they predate this work and are not caused by it. I did not investigate them.

**Not done:**
- I did not regenerate or backfill finance's numbers. Cases affected since 2025-09-02 need a backfill, because the hourly sync only upserts rows whose value changed.
- The two open questions from my earlier analysis are still open. Case 5363 kept accruing while Stable, and it dropped on Sep 5 without explanation. The fix restores the old cut-off, but I have not checked these against the case rows in the database.

I have not committed. The diff is one line in the service and a 27-line test addition.

----- next turn -----

The TypeError came from projects whose `annual_employee_cost` or `business_year_hours` is NULL. `get_hourly_rate` divided by those values without checking them. Both fields are nullable, and the model's defaults only apply on insert, so older rows stay NULL. A case on one of those projects got no cost and logged the error on every run.

**Changes:**
- **`src/dispatch/project/models.py`**: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic schema use them, so the values can't drift apart. The values themselves are unchanged.
- **`src/dispatch/case_cost/service.py`**: `get_hourly_rate` substitutes the default only when the value is `None`. A real `0` is kept, so zero employee cost still gives a zero rate.
- **`tests/case_cost/test_case_cost_service.py`**: two new tests.
  - `test_get_hourly_rate_uses_project_defaults_when_unset` covers both fields unset, only hours unset, and only cost unset.
  - `test_calculate_case_response_cost_with_unset_project_values` checks that a case on such a project still gets a positive cost. Before the fix it raised the same `'NoneType' / 'NoneType'` error.

**Test results** (`python -m pytest`):
- `tests/case_cost`: 22 passed.
- Full suite: 362 passed, 4 skipped, 8 failed. The 8 failures are the same ones that already failed before my changes (the `tests/ai` tests, one database filter test and one entity test). The count went from 360 to 362 because of the two new tests.

**Left alone:**
- `src/dispatch/incident_cost/service.py:131-133` has the same unguarded division. Incident costs will hit the same error on projects with NULL values. I didn't change it because you asked about the case cost job. It's a small change if you want it.
- A `business_year_hours` of `0` is not `None`, so it still raises `ZeroDivisionError`. Nothing in the logs shows that case. I didn't add a guard for it.
- The affected project or projects are not named in the logs. Setting the values in the database would also stop the errors. I haven't changed any data.

I haven't committed.

----- next turn -----

## Recap

**Cost inflation:** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For cases past the new/triage stage, the cost cut-off moved from the earliest of escalated, stable and closed to the latest. Each participant's time in role therefore ran until the last of those timestamps, which inflated the case response cost. The commit reached production in image `main-65f7df6e`, which rolled out on 2025-09-02 at about 18:14 UTC. The scheduler restart at 18:15:30 confirms the rollout. The first flagged inflated Stable case in the logs is 2025-09-03; the log has no earlier flags, so the first inflated cost may be a few hours before that. I did not verify it against the case rows.

**Fix:** I reverted the line to `min(timestamps)`. A regression test in `tests/case_cost/test_case_cost_service.py` fails on the broken code and passes with the fix.

**TypeError:** The hourly job raised `unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate`, because `annual_employee_cost` was NULL on some projects. Those cases got no cost. I made `get_hourly_rate` fall back to the project model defaults (50000 and 2080) when a value is `None`. I moved those defaults into named constants in `src/dispatch/project/models.py`, and the column defaults and schema use the same constants. Two new tests cover the fallback.

**Test results:** `tests/case_cost` passes (22 tests). The full suite has 362 passing and 8 failing. The 8 failures are in `tests/ai`, one database filter test and one entity test. They also fail without my changes, so they predate this work.

**Open items:**
- `src/dispatch/incident_cost/service.py` has the same unguarded division, so incident costs will fail the same way on projects with NULL values. I did not change it.
- A `business_year_hours` of `0` still raises `ZeroDivisionError`. Nothing in the logs shows that case.
- The affected projects are not named in the logs, and the database rows are unchanged. Finance will need a backfill for inflated cases.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost