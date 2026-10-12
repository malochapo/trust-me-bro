**Root cause: commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02). Production picked it up in the deploy of image `main-65f7df6e` on 2025-09-02 at 18:14–18:15Z.**

**The change**

It is a one-word change in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). The cost cut-off for a case that is no longer new or in triage went from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. These columns are only ever set, never cleared (`case/flows.py`).

- **Before:** cost stopped accruing at the earliest of those timestamps, so a case's cost froze at its first hand-off.
- **After:** the cut-off is the latest timestamp. Any case that has more than one of them, or that gets a new one later, is costed through the later time.

That makes a case that has been escalated and then stable, or re-stabilised, accrue cost for the extra period. The hourly rates and cost models are untouched, which matches what you saw.

**Why I think this is it, from the logs**

- **Deploy timing:**
  - `main-65f7df6e` reached the scheduler at 2025-09-02 18:15Z, and `20f33137` is in that build.
  - The previous production image, `main-3e0445ff` from 08-27, does not contain it.
  - No rollback appears in the events log.
- **Before the deploy:** `cost-sync.log` shows 0 flagged cases and no large step jumps from 08-25 through 09-03 11:20.
- **After the deploy:** all five large jumps were on cases in Stable status:

| Case | Time (UTC) | Classic cost |
|---|---|---|
| 5284 | 09-03 11:20 | $3,331 → $8,804 |
| 5327 | 09-05 16:20 | $2,244 → $5,539 |
| 5264 | 09-08 10:20 | $3,285 → $11,987 |
| 5363 | 09-09 12:20 | $2,261 → $6,241 |
| 5406 | 09-12 11:20 | $1,975 → $4,945 |

- **Case 5363:**
  - It accrued about $145 an hour from 09-04 09:20.
  - It froze at $2,261 from 09-05 16:20 to 09-09 12:20, when it was stable.
  - It then jumped by about $4,000 in a single hour.
- **Scheduler:** `calculate_cases_response_cost` runs hourly and recomputes stable cases. That is how the bad cut-off lands in the database, and the sync job only copies it.

**What I ruled out**

- **Deploy `51546e13` (09-04, Slack canvas):** it came after the first jump (09-03). Its commit is unrelated to cost.
- **case-cost-sync 1.4.2 → 1.5.0 on 09-01 10:20Z:** it changed the page size from 50 to 100, and it predates the first anomaly. After the upgrade there were no flagged cases until 09-03, after the Dispatch deploy.
- **The 09-05 drop on 5363 ($3,425 → $1,243):** this is the existing rule that compresses time past 24 hours. It is not a bug.

**What I could not confirm**

The logs don't contain the case timestamps. So I can't show exactly which timestamps case 5363 held on 09-09, for example a re-stabilisation. I can only show that the jump pattern matches the `min` → `max` change. To confirm, query the `escalated_at`, `stable_at` and `closed_at` columns for cases 5284, 5327, 5264, 5363 and 5406.

**Fix and cleanup**

I haven't changed any code. The likely fix is to revert to `min`, or to define the cut-off explicitly, for example the timestamp of the transition that put the case into its current status. The warehouse then needs backfilling. Cases that went stable or escalated since 09-02 18:14Z have inflated stored amounts. The scheduler skips stable cases whose cost was updated after `stable_at`, so those values may not correct themselves. I can draft the fix and a regression test when you're ready.

----- next turn -----

I reverted the cost cut-off to `min(timestamps)` and added a regression test. Under `min`, the `tests/case_cost` suite passes (20 tests). I haven't committed anything.

- **Fix:** `src/dispatch/case_cost/service.py` is back to `participant_role_renounced_at = min(timestamps)`, which undoes `20f33137`.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` is in `tests/case_cost/test_case_cost_service.py`. It sets `stable_at`, `escalated_at` and `closed_at` at different times and asserts the cost stops at the earliest one. The existing tests only ever set one timestamp, so they could never tell `min` from `max`.
- **Check:** with the source change stashed (so `max` was back), the new test failed and the other 19 passed. So it does catch this bug.

Two things still need doing:
- **Deploy:** the fix has to reach production, since the scheduler recomputes costs from the deployed code.
- **Backfill:** cases that went stable or escalated since 2025-09-02 18:14Z have inflated stored amounts. Cases 5284, 5327, 5264, 5363 and 5406 are known examples, and there may be more with smaller jumps. The scheduler skips stable cases whose cost was updated after `stable_at`, so those amounts may not correct themselves after the deploy. The warehouse also needs re-syncing once Dispatch has the right values.

----- next turn -----

The TypeError is fixed: cases in projects with a missing annual employee cost or business year hours now get a cost. The `tests/case_cost` suite passes (21 tests, including the new one), and nothing is committed.

**Cause:** all 708 TypeErrors in `scheduler.log` are the same one, `unsupported operand type(s) for /: 'NoneType' and 'int'`. They come from `get_hourly_rate`, which divides `project.annual_employee_cost` by `project.business_year_hours` (`case_cost/service.py`, called from `calculate_case_response_cost_new` and the classic version). Both columns are nullable, and their defaults of 50000 and 2080 only apply when a row is inserted. A project whose `annual_employee_cost` is NULL therefore crashes the division. Because the job catches and logs the error per case, those cases just never get a cost.

**Unknown:** the logs don't say which project it is, or what set the value to NULL around September 8. Checking the project settings would answer that.

**Fix:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` now substitutes the `Project` column defaults for whichever value is None. It reads them from the model (`Project.annual_employee_cost.default.arg`) rather than hardcoding them.

**Test:** `test_get_hourly_rate__missing_values_use_project_defaults` covers each value missing alone and both missing. I didn't run it against the old code, but the old code divides by None in every missing-value case.

`incident_cost/service.py:131` has an identical `get_hourly_rate` with the same weakness. I left it alone because you scoped this to cases. Incident costs would hit the same error if an incident's project has the same NULL, so it's worth the same fix.

----- next turn -----

**Recap**

- **Symptom:** from early September, the case costs that case-cost-sync copied into the finance warehouse jumped by several times in a single hourly step. The example case was dispatch-default-security-5363, which went from $2,261 to $6,241 on September 9.
- **Root cause:** commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. A case with more than one of them was then costed through the latest one instead of the earliest.
- **Deploy:** the commit went to production in `main-65f7df6e`, which reached the scheduler on 2025-09-02 at 18:15Z. The later deploy `main-51546e13` (09-04) and the case-cost-sync 1.5.0 upgrade (09-01) don't explain the jumps.
- **Evidence:**
  - Before the deploy, the sync logs show no flagged cases.
  - Afterwards there are five large jumps, all on Stable cases: 5284 on 09-03, 5327 on 09-05, 5264 on 09-08, 5363 on 09-09 and 5406 on 09-12.
- **Fix:** I reverted the cut-off to `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. It fails on the `max` code and passes on `min`.
- **Still to do:** deploy the fix, then backfill cases that went stable or escalated since 09-02 18:14Z, then re-sync the warehouse.
- **Unconfirmed:** the logs don't hold case timestamps, so the exact trigger for each jump isn't shown. A query on those cases' timestamp columns would confirm it. `FIRST_INFLATED` is also only the first large jump visible in the sync logs. Smaller inflation on other cases could have started earlier. I did check the window from the deploy to that jump and found nothing else out of the ordinary.
- **Separate issue:** from 09-08 the hourly job logged 708 `TypeError`s, all from `get_hourly_rate` dividing a NULL `annual_employee_cost`. It now falls back to the `Project` model defaults, with a new test. `incident_cost/service.py` has the same weakness and is not fixed. The logs don't show which project is affected or what set the value to NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost