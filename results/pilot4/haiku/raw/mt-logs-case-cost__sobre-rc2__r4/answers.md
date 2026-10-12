**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed one line in `src/dispatch/case_cost/service.py:353` from `min(timestamps)` to `max(timestamps)`. Accrual now runs to the latest of the stable, escalated, and closed timestamps instead of the earliest. For any case that was escalated and later marked stable (or closed after stable), the participant-role time runs to the later timestamp, so classic costs get inflated for that case.

**Deploy:** that commit shipped in `registry.example.com/dispatch:main-65f7df6e`. Events show the `dispatch-web` and `dispatch-scheduler` rollouts to it on 2025-09-02 at 18:14–18:15 UTC. It was the only Dispatch deploy that day. The later `main-51546e13` deploy (Sep 4, 16:52) came after the first jump, so it isn't the trigger.

**Why it matches the data:**
- No non-accrual jumps appear before Sep 2. Normal hourly accrual is about +145 per hour per case, and the only jumps larger than +400 in a single sync are on Sep 3 (case 5284, 3331→8804), Sep 5 (5327, 2244→5539), Sep 8 (5264, 3285→11987), Sep 9 (5363, 2261→6241) and Sep 12 (5406, 1975→4945).
- Case 5363's jump happened at the moment it was marked stable, which fits a case with both an escalated and a stable timestamp: the cut-off jumps from the escalation time to the stable time.
- The first jump is on Sep 3, not Sep 9, so the 5363 example is one of several.

**Ruled out:**
- **cost-sync 1.4.2 → 1.5.0 (Sep 1):** the only change I found is the page size (100 instead of 50). It still reads all 200 cases and its row counts are unchanged, so it doesn't produce the inflation. The rest of the sync pattern is also unchanged.
- **Scheduler or cost-model config:** no changes to rates or cost models appear in the logs or in the repo's recent commits.

**Caveat:** I inferred the escalated-plus-stable mechanism from the code and the timing, not from the database. Confirming it means checking the `escalated_at` and `stable_at` values for case 5363 (and one of the other cases above).

**Suggested fix (not applied, as requested):** revert the line to `min(timestamps)`, which freezes accrual at the first stable/escalated/closed event. The commit message's stated intent ("latest status timestamp") doesn't match what the code does, so the intent needs confirming with Jordan Lee before the revert. Afterwards, the affected costs for Sep 2 onward need recalculating and re-syncing to the finance warehouse.

----- next turn -----

The fix is in and tested, but I haven't committed it.

**The fix:** `src/dispatch/case_cost/service.py:353` now uses `min(timestamps)` again, instead of `max`. Accrual stops at the earliest of the escalated, stable, and closed timestamps, which is what it did before commit `20f33137`.

**The regression test:** `test_get_participant_role_time_seconds_stops_at_first_end_event` in `tests/case_cost/test_case_cost_service.py`. It sets up a case escalated 2 hours ago and marked stable 1 hour ago, with the assignee assumed 3 hours ago. Cost should count 1 hour (3600 s), not 2 hours. I checked that it catches the bug: with `max` it fails with `7200.0 == 3600`, and with `min` it passes.

**Results:**
- `python -m pytest tests/case_cost`: 20 passed (19 existing plus the new test).
- Full `python -m pytest`: 360 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on the unmodified code, so my change didn't cause them, but I didn't investigate them.

**Things to decide:**
- The commit message for `20f33137` says "use the latest status timestamp", which contradicts what the `min`/`max` logic is meant to do. I chose `min` because it matches the finance baseline from before September 2. If Jordan Lee had a different intent, that needs a conversation before this merges.
- Costs for September 2 onward are still inflated in the finance warehouse. The fix stops new accrual, but the affected rows need recalculating and re-syncing.

----- next turn -----

The TypeError is fixed and covered by a test. Nothing is committed.

**Cause:** some project rows have `NULL` in `annual_employee_cost` or `business_year_hours`. `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides those values with no fallback, so every case in that project raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The model's defaults (`50000` and `2080`) only apply when a row is inserted, so they don't fix rows that were saved with `NULL`. The logs don't name the project, and I can't query the database, so I haven't confirmed which project or how its values became `NULL`. There's also no Dispatch deploy on or near September 8, so the change most likely came from data, not code.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic base use these constants, so the values can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default when its value is `None`. Each field falls back independently.

**Test:** `test_get_hourly_rate_falls_back_to_project_defaults` in `tests/case_cost/test_case_cost_service.py`. It covers both values missing, each one missing alone, and a full response-cost calculation that must return a positive cost. With the old `get_hourly_rate`, it fails with the same `TypeError` from the logs.

**Results:**
- `python -m pytest tests/case_cost`: 21 passed.
- Full `python -m pytest`: 361 passed, 8 failed, 4 skipped. The 8 failures are the same ones as before (AI service, one database test, one entity test), and they also fail on the unmodified code.

**Left alone:**
- `src/dispatch/incident_cost/service.py:131` has the same unguarded division. Incident costs will fail the same way for any project with missing values. I didn't change it because you asked about case costs. Say the word and I'll apply the same fallback there.
- `individual/service.py` still hardcodes `50000` and `2080`. It works, but it could use the new constants.

----- next turn -----

The post-deploy diffs are mostly normal accrual, with a few oddities I can't explain (some costs drop, and the bug can only raise them). Here's the recap, with the six lines at the end as requested.

**Recap: case response cost inflation and hourly TypeError**

- **Inflated costs.** Commit `20f33137d` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Accrual then ran to the latest of the escalated, stable, and closed timestamps, not the earliest. Cases that were escalated and later marked stable were overcharged. The change shipped in `main-65f7df6e` on 2025-09-02 at 18:14 UTC. Finance's warehouse is still carrying the inflated rows.
- **Inflated-cost date.** The first large inflation in the sync logs is on 2025-09-03 (case 5284, 3331→8804). I can't rule out a smaller inflation on the evening of September 2 from the logs alone, because normal accrual varies by project rate.
- **Hourly TypeError.** Some projects have `NULL` in `annual_employee_cost` or `business_year_hours`. `get_hourly_rate` divided without a fallback, so cases in those projects raised the error every hour. The likely cause is that those values were saved as `NULL` after insert, since model defaults only apply on insert. The logs don't name the project, and I haven't confirmed how the values became `NULL`. No deploy happened near September 8, which suggests a data change.
- **Fix (uncommitted).** `min` is restored, and `get_hourly_rate` falls back to the project model defaults (`DEFAULT_ANNUAL_EMPLOYEE_COST = 50000`, `DEFAULT_BUSINESS_YEAR_HOURS = 2080`), which are now shared constants in `project/models.py`.
- **Tests.** Two regression tests were added in `tests/case_cost/test_case_cost_service.py`. Both fail on the old code and pass on the fix. `python -m pytest tests/case_cost` passes (21 tests). The full suite has 8 failures that also fail on the unmodified code (AI service, one database test, one entity test), so I didn't touch them.
- **Open items.** `incident_cost/service.py` has the same unguarded division, and I haven't fixed it. Finance also needs the affected case costs recalculated and re-synced. The logs also show some case costs dropping, which I haven't explained.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```