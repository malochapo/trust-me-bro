**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee) changed `min(timestamps)` to `max(timestamps)`. The change is in `get_participant_role_time_seconds`, in `src/dispatch/case_cost/service.py:353`. The deploy that shipped it was `main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z. I'm confident in that. What I couldn't confirm is the exact event sequence behind case 5363's jump.

**What the code does:** the cost stops counting a participant's time at the earliest of `stable_at`, `escalated_at` and `closed_at`. The commit message says "latest", but the code before it was deliberately using the earliest. With `max()`, any case with more than one of those timestamps is costed up to the latest one instead of the first one. Cases with only one timestamp are unaffected, which fits only a few cases being flagged.

The scheduler only recalculates stable cases whose cost was last updated at or before `stable_at`. When the cost is recalculated, it jumps to the new, later cut-off. That matches the sudden increases in the sync log, not a gradual drift.

**Why this deploy:**
- **Commit order:** `20f33137` (2025-09-02 09:29 PDT) is a direct ancestor of `65f7df6e`. The previous deploy, `main-3e0445ff` on 08-27, predates it.
- **Rollout:** the `65f7df6e` db-upgrade job completed. The web and scheduler pods pulled the image and started, with no errors. The scheduler began at 18:15:30Z.
- **Later deploys:** `51546e13` (09-04, and a scheduler restart on 09-10) also contains the change, but it is not where it came from.
- **First symptom:** the first "flagged for review" warning in `cost-sync.log` is 09-03 11:20Z, the first sync after the deploy. There were none before.
- **Flagged cases:** all five flags are Stable cases: 5284, 5327, 5264, 5363 and 5406. Each is a jump of +147% to +265%, and 5363 is the 2261 → 6241 jump on 09-09 12:20Z.
- **Case 5363:** its cost also dropped from 3425 to 1243 on 09-05 and was flat from 09-05 16:20 until 09-09. The logs don't show the case's status history, so I can't say exactly which timestamps combined to give 6241. Querying the case's `stable_at`, `escalated_at` and `closed_at` would settle it.

**Red herrings I ruled out:**
- **case-cost-sync upgrade:** it went from 1.4.2 to 1.5.0 on 09-01, before any flags, and only changed page size (50 → 100). The cost values come from Dispatch's API.
- **`TypeError ... NoneType / int` in `get_hourly_rate`:** these scheduler errors started 09-08 and affect the new cost model's project settings. They are separate from the classic-cost jump.
- **Database restart on 09-06:** it caused one failed task run and nothing more.

**Fix and cleanup:** the fix would be to revert to `min()`, then correct the inflated costs already in Dispatch and in the finance warehouse for affected stable cases. I haven't changed any code, as you asked.

----- next turn -----

The fix is in and the regression test works, but 3 other tests in `tests/case_cost` error out because of a missing dependency in this environment. I could only run the suite against a stand-in for `slack_sdk`, so it wasn't a clean run.

**The fix:** in `src/dispatch/case_cost/service.py`, `max(timestamps)` is back to `min(timestamps)`. The cost now stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.

**The new test:** `test_get_participant_role_time_seconds__uses_earliest_cutoff` in `tests/case_cost/test_case_cost_service.py`.
- **Setup:** a closed case with `stable_at` at +2h, `escalated_at` at +5h and `closed_at` at +10h after the participant assumed their role.
- **Check:** the participant's time must be exactly 2h times the engagement multiplier.
- **Before and after:** it fails with the old `max()` code and passes with `min()`. The existing test only used a single timestamp, which is why it missed the bug.

**Test run:**
- **Dependency:** `slack_sdk` isn't installed in the venv and there's no pip. I ran the tests with a minimal stub of it in `/tmp/sobre-stub`, outside the repo, so nothing in the repo or environment changed.
- **Results:** 17 tests pass, including the new one. The 3 errors are `test_fetch_case_event__enabled_plugins`, `test_fetch_case_event__no_enabled_plugins` and `test_update_case_participant_activities__create`. The Slack plugins fail to load against the stub, so the errors come from the stub and not from my change. I didn't run them against a real `slack_sdk`.

The costs already stored in Dispatch and the warehouse for affected stable cases (5284, 5327, 5264, 5363 and 5406) are still inflated. They would only be corrected by recalculation, and the scheduler skips stable cases whose cost was updated after `stable_at`. You'll probably need a one-off recalculation and a re-sync, and I haven't done either.

----- next turn -----

The cost job's `TypeError` is fixed, and cases in projects with unset cost values now get a cost. The 3 pre-existing errors are the same Slack-plugin ones as before, which come from the `slack_sdk` stand-in. I ran the tests against a stand-in because the real `slack_sdk` isn't installed in this environment.

**Cause:**
- **Where it fails:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The error is `unsupported operand type(s) for /: 'NoneType' and 'int'`, raised from `calculate_case_response_cost_new` via `get_hourly_rate`.
- **Why it's null:** the two columns are nullable. The `default=` on `Project` only applies when the value is omitted, so a project saved with an explicit null keeps null. The API's `ProjectBase` schema also allows `None`.
- **Why since 09-08:** a project named "fraud" first appears in the scheduler's per-project output on 09-08 at 14:54, and the first `TypeError` is at 15:55. I inferred that the new project has null values. I couldn't see the project's settings directly, so that part isn't confirmed.
- **Scale:** there are 1,416 of these errors in the log. The job's per-case `try/except` catches each one, so those cases never got a cost saved.

**Fix:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` now fills in each missing value from the project model's own column default (50000 for annual cost, 2080 for business-year hours). It fills them independently, so a project with only one value set keeps that value.

**Tests:** I added `test_get_hourly_rate__unset_values_use_project_defaults`, which checks four combinations of set and unset values. With the fix, the `tests/case_cost` suite shows 21 passed. With the fix removed, 3 of the 4 new cases fail. The fourth is the all-values-set case, which passes either way.

- **Incident cost has the same bug:** `incident_cost/service.py` has an identical `get_hourly_rate`, so a null project would break incident costs the same way. I left it alone because you only asked about cases.
- **Underlying data:** the "fraud" project still has null values in the database. Saving real values there, or adding a non-null constraint, would stop this from coming back for other code that reads those columns.

----- next turn -----

Drops are normal background (about 15 a day, before and after the deploy), so only the upward jumps on Stable cases mark the bug.

## Recap

**Inflated costs**
- Since early September, the warehouse has been getting case response costs that are several times too high. Case `dispatch-default-security-5363` went from $2,261 to $6,241 on 09-09.
- The cause was commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off"). It changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function stops counting a participant's time at the earliest of `stable_at`, `escalated_at` and `closed_at`, and `max()` made it use the latest.
- Only cases with more than one of those timestamps are affected. The scheduler recalculates stable cases only when their stored cost is older than `stable_at`, so the cost jumps in one step once that recalculation happens.
- **Deploy:** the code first reached production in `main-65f7df6e`, rolled out 2025-09-02 at about 18:14–18:15Z. The previous deploy, `3e0445ff`, predates the commit. Image `51546e13` (09-04, and a scheduler restart on 09-10) also contains it.
- **Evidence:** the first "flagged for review" warning is case 5284 at 2025-09-03 11:20Z, and there were none before. All five flags are Stable cases: 5284, 5327, 5264, 5363 and 5406.
- **Unexplained:** I couldn't reconstruct case 5363's exact status history from the logs, so I can't say which timestamps produced 6241. A query of that case's three timestamps would settle it.
- **Fix:** `min()` is restored, with a regression test (`test_get_participant_role_time_seconds__uses_earliest_cutoff`) that fails on the old code.
- **Still to do:** the stored costs for the five affected cases are still inflated in Dispatch and the warehouse. They need a one-off recalculation and a re-sync, which I haven't done.

**Hourly `TypeError`**
- **Symptom:** the scheduler's case cost job has logged `unsupported operand type(s) for /: 'NoneType' and 'int'` every hour since 09-08, about 1,416 times in total.
- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. The error text puts `None` on the left of the division, so `annual_employee_cost` is the missing value. Both columns are nullable, and a project saved with an explicit null keeps null.
- **Likely project:** a "fraud" project first appears on 09-08 at 14:54 and the first error is at 15:55. I inferred that this project has null values but couldn't see its settings.
- **Fix:** each missing value now falls back to the project model's default (50000 and 2080), with a parametrized test.
- **Related:** `incident_cost/service.py` has the same unguarded `get_hourly_rate`, and I haven't changed it.

**Test status:** `slack_sdk` isn't installed in this environment, so I ran the tests against a stand-in. 21 tests in `tests/case_cost` pass. Three Slack-plugin tests error, and the cause is the stand-in. The suite hasn't been run cleanly against the real `slack_sdk`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost