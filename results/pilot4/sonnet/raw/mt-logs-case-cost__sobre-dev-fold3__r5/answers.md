**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off". It changed one line in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`) from `min(timestamps)` to `max(timestamps)`.

- **What the code does:** the function collects `stable_at`, `escalated_at` and `closed_at`, then uses the result as the point where the case stops accruing cost. The original `min()` stopped the clock at the earliest of those events. The comment still says "the earliest relevant timestamp" and "before the case was marked as stable or closed".
- **Effect of `max()`:** the clock now runs to the latest timestamp, so cost keeps accruing past the point where the case went stable.
- **Why it only hits some cases:** a case with only one of these timestamps gives the same result under `min` and `max`. I think the affected cases carry a second, later timestamp (for example `closed_at` or `escalated_at`). I couldn't confirm that, because the logs don't include those fields.

**The deploy:** `main-65f7df6e`, rolled out on 2025-09-02. Its DB upgrade job ran at 18:14Z and the web and scheduler pods rolled by 18:15Z. It is the first deploy after the commit landed that morning (09:29 PDT), so it is the first image containing `20f33137`. The next deploy, `main-51546e13` on Sep 4 at 16:52Z, still carries the change. The previous deploy, `main-3e0445ff` on Aug 27, predates it.

**Evidence from the logs:**
- Across the whole window, `cost-sync.log` has only five hourly increases above $400 for a single case. All five are on Stable cases and all come after the Sep 2 deploy:

  | Case | Sync (UTC) | Cost change |
  |---|---|---|
  | 5284 | Sep 3 11:20 | $3,331 → $8,804 |
  | 5327 | Sep 5 16:20 | $2,244 → $5,539 |
  | 5264 | Sep 8 10:20 | $3,285 → $11,987 |
  | 5363 | Sep 9 12:20 | $2,261 → $6,241 |
  | 5406 | Sep 12 11:20 | $1,975 → $4,945 |

  Cases 5284 and 5327 jumped on Sep 3 and Sep 5, before 5363 did on Sep 9.
- There were no such jumps from Aug 25 through the Sep 2 deploy.
- Hourly decreases are normal in the earlier data. They match the 8-hours-per-day adjustment for long-running cases, so the $3,425 → $1,243 drop on case 5363 on Sep 5 is not part of this problem.
- Case 5363 grew steadily at about $145 per hour until it was marked Stable. At that point the cut-off moved later instead of freezing the cost.

**Ruled out:**
- The finance job's upgrade from 1.4.2 to 1.5.0 (page size 50 → 100) happened on Sep 1 at 10:20Z. There were no anomalies for two days after it.
- Nothing in `events.log` shows a rollback or a crash loop.

**What's left:**
- **Confirm the mechanism:** I haven't confirmed which timestamps the affected cases carry. A query of `stable_at`, `escalated_at` and `closed_at` for cases 5284, 5327, 5264, 5363 and 5406 would settle it.
- **Fix and backfill:** the fix is probably a revert to `min()`. The warehouse rows for Stable cases changed since Sep 3 need recomputing, and Dispatch only recalculates them on its own if the cost job re-runs for those cases. I haven't changed any code.

----- next turn -----

I reverted the one-line change in `src/dispatch/case_cost/service.py`, so `max(timestamps)` is back to `min(timestamps)`. I also added a regression test. Nothing is committed, and I haven't touched the warehouse.

**Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a stable case that also has later `escalated_at` and `closed_at` timestamps, and requires the participant's role time to stop at `stable_at`. The existing stable-cutoff test only set `stable_at`, which is why `min` and `max` looked the same and nothing caught the change.

**Test runs:**
- With the fix, all 20 tests in `tests/case_cost` pass.
- With the fix stashed (the buggy `max()`), the new test fails and the other 19 pass.

I only ran `tests/case_cost`, not the full suite.

**Still to do:**
- **Deploy:** the fix has to ship. Until it does, production keeps overcharging cases as they go Stable.
- **Warehouse:** rows for cases that went Stable since Sep 3 (5284, 5327, 5264, 5363 and 5406, plus any not flagged) need recomputing. Please confirm with finance whether the next sync overwrites them or whether they need a manual backfill.

I haven't committed. Say if you want me to commit this.

----- next turn -----

Cases in a project with an empty annual employee cost or business year hours now get a cost instead of a TypeError. `tests/case_cost` passes (22 tests). I haven't committed anything.

**Cause:** `get_hourly_rate` (`src/dispatch/case_cost/service.py`) divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the model's default of 50000 / 2080 only applies when a row is inserted. The project API schema also accepts `null` for both. A project with a NULL value makes the division fail. The logged message is `'NoneType' and 'int'`, so it was `annual_employee_cost` that was NULL, not the hours.

**Effects in the scheduler:**
- **Scope of the failure:** the error is caught per case in `calculate_cases_response_cost`, so only cases in that project fail (the logs show 708 tracebacks). The first one is 2025-09-08 15:55.
- **What those cases lose:** the new-model cost is calculated first and raises, so those cases also never get their classic cost updated.
- **Why Sep 8:** I can't tell from the logs which project it is or why it started that day. A settings change that day is plausible, but I didn't verify it.

**Fix:** `get_hourly_rate` now takes the `Project` model's own column default (50000 or 2080) for whichever value is missing, so the defaults aren't hardcoded a second time. It still returns `ceil(cost / hours)`.

**Tests:**
- `test_get_hourly_rate__missing_project_values_use_defaults` covers each value missing alone and both missing.
- `test_calculate_case_response_cost__project_without_rate_settings` checks that a case in such a project gets a cost.
- Both fail without the fix. That check also stashed the earlier `min()` revert, so the earlier regression test failed in the same run.

`incident_cost/service.py` has an identical `get_hourly_rate` with the same weakness. You only asked about cases, so I left it alone. It's a small change if you want it.

Separately, you may want to find the project with the NULL cost and set a real value, so the default isn't silently standing in for it.

----- next turn -----

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function sets the point where a case stops accruing cost, taken from `stable_at`, `escalated_at` and `closed_at`. With `max()`, a case with a later timestamp than `stable_at` kept accruing cost after it went Stable.
- **Deploy:** the first image containing the commit was `main-65f7df6e`, rolled out Sep 2 at about 18:14Z. The Sep 4 deploy (`main-51546e13`) still carried the bug.
- **Evidence:** the first jump in `cost-sync.log` is case 5284 on Sep 3 at 11:20Z ($3,331 → $8,804). Four more Stable cases jumped on later days. There were no such jumps before the deploy. I saw no sign that the finance job's Sep 1 upgrade (1.4.2 → 1.5.0) or a rollback was involved.
- **Date caveat:** "first inflated" is the first jump I could see in the logs, an hourly increase above $400. Smaller inflations earlier that day would not stand out, and I didn't check for them.
- **Fix:** reverted to `min()`, with a regression test for a stable case that also has later `escalated_at` and `closed_at`. Without the fix, that test fails.
- **Still open:**
  - The fix has to be deployed.
  - Warehouse rows for cases that went Stable since Sep 3 need recomputing.
  - The mechanism is inferred, because the logs don't show those timestamps for the affected cases.

**Hourly TypeError**
- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`, and a project had `annual_employee_cost` NULL. The columns are nullable, and the model default only applies on insert. There were 708 tracebacks, the first at 2025-09-08 15:55. Only that project's cases failed, and they also lost their classic cost update.
- **Fix:** a missing value now falls back to the `Project` model default (50000 and 2080), with tests.
- **Not done:** `incident_cost/service.py` has the same weakness. I haven't touched it. I couldn't tell from the logs which project it is or why it started Sep 8.

Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost