The root cause is commit `20f33137`, which shipped to production in the Sep 2 18:14Z deploy of image `dispatch:main-65f7df6e`.

**Root cause**

`20f33137` is "fix(case_cost): use the latest status timestamp as the cost cut-off", authored Sep 2 at 09:29 PDT. It changes one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`, from `min(timestamps)` to `max(timestamps)`. The `timestamps` list holds `stable_at`, `escalated_at` and `closed_at`.

The surrounding code is unchanged. Its comment still says "Determine the earliest relevant timestamp for cost calculation cut-off", and a later comment refers to the cut-off as when the case was "marked as stable or closed". Cost is meant to stop accruing at the first of those events. With `max`, any case that has more than one of these timestamps keeps accruing until the latest one.

Case 5363 fits this, though I'm inferring the escalation. From the cost-sync log:
- Its classic cost grew about $145/hour from Sep 4 until it froze at $2,261 on Sep 5 at 16:20Z, which is when the old `min` cut-off applied.
- It stayed at $2,261 until Sep 9 at 12:20Z, when it was marked stable. The cost then jumped to $6,241 (+176%).
- That is what `max` gives if an earlier cut-off timestamp was already set. The code now counts time up to the later stable timestamp instead of stopping at the earlier one. The logs don't show 5363's `escalated_at` or `closed_at`, so that earlier timestamp is my inference.

Nothing changed in the rates or cost models. The same recomputation produces the inflated numbers whenever case costs are recalculated.

**The deploy**

| Time (UTC) | Event |
|---|---|
| Aug 27 17:03 | Image `main-3e0445ff` rolled out. It predates the commit and is not a suspect. |
| Sep 2 16:29 | `20f33137` committed (09:29 PDT). |
| **Sep 2 18:14–18:15** | **Image `main-65f7df6e` rolled out (db-upgrade, then web, then scheduler). This is the deploy that shipped the bug.** `20f33137` is an ancestor of it. |
| Sep 4 16:52 | Image `main-51546e13` rolled out. It also contains the bug and did not introduce it. |

The `main-65f7df6e` rollout also carried other commits: `5670487c` (remove dependabot), `beb60cc4` (entity JSONPath perf) and `65f7df6e` itself (the UI channel-case filter), plus a few dependency bumps and a database filter refactor. None of them touch `case_cost`.

**Evidence from the logs**

- The cost-sync job first flagged a jump on Sep 3 at 11:20Z, after the Sep 2 deploy. The flags are case 5284 on Sep 3, 5327 on Sep 5, 5264 on Sep 8, 5363 on Sep 9 and 5406 on Sep 12. All are Stable cases with increases of 147–265%. No flags appear before Sep 3.
- The finance job moved from 1.4.2 to 1.5.0 on Sep 1, but that is not the cause. Nothing was flagged for two days after the upgrade, and the first flag came after the Dispatch deploy.

**What I haven't verified**

I haven't run the function against case 5363's real timestamps, because I don't have that data. Before you fix anything, I'd check the case's `escalated_at`, `closed_at` and `stable_at` in the database. I'd also recompute the affected Stable, Escalated and Closed cases to see which warehouse rows need correcting. I haven't changed any code.

----- next turn -----

I've fixed it and added a regression test. All 20 tests in `tests/case_cost` pass with the fix. The new test fails when I revert the fix and passes when I restore it. I haven't committed anything.

- **Fix:** In `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds()` goes back to `min(timestamps)`. Cost stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py` sets all three timestamps to different times, with escalation first. It asserts that cost stops at the escalation time. The existing stable-time test only set `stable_at`, which is why it never caught the `max` change.

**Still to do**

- **Deploy:** The fix isn't live until it's deployed, and the warehouse rows computed since the Sep 2 18:14Z deploy are still inflated. Finance will need to recompute or re-sync the affected cases, mainly Stable, Escalated and Closed ones.
- **Not run:** I ran only `tests/case_cost`, not the full suite.
- **Unverified:** I still haven't checked case 5363's actual timestamps in the database.

----- next turn -----

The TypeError is fixed and covered by a new test. All 21 tests in `tests/case_cost` pass. With the `src` changes stashed, the new test fails (the earlier regression test fails too, because the stash also reverts the `min` fix). Nothing is committed.

**Cause**

`get_hourly_rate()` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns on `Project` are nullable. The column defaults only apply at insert, so a project with NULL in either column raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The traceback runs through `calculate_case_response_cost_new`, which is called from the hourly `calculate_cases_response_cost` job. That job catches the error per case, logs it and moves on. The affected cases get no cost update, and the log shows 708 occurrences of this TypeError.

I couldn't tell from the logs why it started on Sep 8. The first error is at 15:55 UTC and none of the logged deploys fall near it, so my guess is a project or its settings changed that day. To confirm, check the database for projects where either column is NULL.

**Fix**

When either value is `None`, `get_hourly_rate` now falls back to the `Project` model's column default. Those defaults are 50000 for the annual cost and 2080 for business year hours. A value that is set is still used as is.

**Test**

`test_get_hourly_rate__missing_project_values_use_model_defaults` covers four cases: both values missing, only the cost missing, only the hours missing, and both set.

**Not changed**

`incident_cost/service.py` has an identical `get_hourly_rate` with the same latent bug. I left it alone since you only asked about case costs. It's a two-line change if you want it.

----- next turn -----

## Recap

**Cost inflation**
- **Root cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. The cost cut-off is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has several of those timestamps keeps accruing cost until the latest one.
- **Deploy:** it shipped in the Sep 2 18:14Z rollout of `dispatch:main-65f7df6e`. The Sep 4 image `main-51546e13` also carries it, but it did not introduce it.
- **Symptom:** case 5363 jumped from $2,261 to $6,241 when it was marked stable on Sep 9.
- **Fix:** `min` is restored, and a regression test sets all three timestamps and asserts the cut-off is the earliest.
- **Cleanup:** warehouse rows computed since the deploy are still inflated and need recomputing. The affected cases are mainly Stable, Escalated and Closed ones.

**Hourly TypeError**
- **Cause:** `get_hourly_rate()` in `case_cost/service.py` divides the project's annual employee cost by its business year hours, and both columns are nullable. The error text is `'NoneType' and 'int'`, so the left operand, the annual employee cost, was NULL. Each affected case failed in the hourly job and got no cost update.
- **Fix:** it now falls back to the `Project` model's column defaults for either missing value, and a new test covers it.
- **Open question:** I couldn't determine from the logs why it began on Sep 8, so check which project has a NULL annual employee cost.
- **Still exposed:** `incident_cost/service.py` has the same bug and is not fixed.

**Status**
- `tests/case_cost` passes, but I haven't run the full suite and nothing is committed.
- I haven't verified case 5363's actual timestamps in the database.

**FIRST_INFLATED caveat:** the cost-sync log's first flagged jump is case 5284 on 2025-09-03. A smaller inflation on Sep 2 between 18:14Z and midnight would not show as flagged, but I found no diff over $400 in that window. The deploy itself was Sep 2 at 18:14Z.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost