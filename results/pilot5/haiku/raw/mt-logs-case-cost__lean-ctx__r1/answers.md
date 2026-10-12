**Root cause:** commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

The `timestamps` list holds a case's `stable_at`, `escalated_at` and `closed_at`. The code uses that list as the cut-off for participant role time. Before the change, the cut-off was the earliest of those timestamps. That was deliberate: commit `200cd428` (June, "adds stable status to cases", #6074) introduced the list with `min`. After the change, the cut-off is the latest one. So once a case has been escalated and later marked stable, every participant's role time is counted up to the stable time instead of stopping at escalation. Costs that should have been frozen keep accruing.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`. That commit is a descendant of `20f33137`, so it contains the change. It rolled out on **2025-09-02 at 18:14–18:15 UTC** to `dispatch-web` (replica set `zrhzjwmzrh`) and `dispatch-scheduler` (`qdd74fpnsl`). The previous production image, `main-3e0445ff`, predates the commit and is not affected.

**How the logs show it:**
- **Case 5363 (dispatch-default-security-5363):** it accrues about 146 an hour from Sep 4 09:20. On Sep 5 at 16:20 it freezes at 2261 (consistent with the cut-off sitting at an escalation time). It stays flat until Sep 9 at 12:20, when it is marked Stable and jumps to 6241 in a single sync. That jump is the cost that accrued between the escalation and the stable time, which the `min` logic would have excluded. After the jump it stays flat again.
- **The same freeze-then-jump pattern** appears on other flagged Stable cases after the deploy: 5284 (3331 → 8804 on Sep 3), 5327 (2244 → 5539 on Sep 5), 5264 (3285 → 11987 on Sep 8) and 5406 (1975 → 4945 on Sep 12). The first flag in `cost-sync.log` is on Sep 3, the first sync after the rollout.

**Limits of this analysis:**
- The logs contain only cost deltas, not the case timestamps. "Escalated, then stable" is inferred from the freeze and jump shape, not read from Dispatch's data. Confirming it needs `escalated_at`, `stable_at` and `closed_at` for case 5363 from the Dispatch database.
- I did not confirm which process runs `calculate_case_response_cost`. The scheduler deploy is in the same window.
- Case 5264 also dropped from 4643 to 3188 on Aug 29, before the commit. I did not explain that.

**Suggested next steps (no code changed):**
1. Revert the `max` back to `min` in `service.py:353`, or define the cut-off more precisely if the intent was the latest status timestamp. A test that escalates and then stables a case, and checks that the cost stays frozen at the escalation time, would have caught this.
2. Re-run the cost sync for the affected cases after the fix, and check with finance whether the inflated `finance.case_response_cost` rows need correcting.

----- next turn -----

Fixed, with a regression test. The fix is not committed.

**The fix:** `src/dispatch/case_cost/service.py:353` goes back to `min(timestamps)`. The cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`, as it was before commit `20f33137`.

**The regression test:** `test_case_cost_stops_at_first_cut_off_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a stable case that was escalated one hour before it was marked stable, with an active participant. It asserts the role time ends at escalation. I checked that it catches the bug: with `max` restored, it fails, and with `min` it passes.

**Test results:**
- `python -m pytest tests/case_cost`: 20 passed, including the new test.
- `python -m pytest` (full suite): 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). I ran those files on a clean checkout of `main` at `51546e13` and the same 8 fail there, so they predate this change and are unrelated to it. I did not investigate them.

**Not done:**
- I did not commit the change or deploy it.
- The finance rows already written with inflated costs (for example case 5363 at 6241) still need correcting. Re-running the cost sync after the deploy will fix the costs going forward, but I have not checked how the sync handles rows it has already written.

----- next turn -----

The hourly `TypeError` comes from a missing project setting, and it's fixed with a regression test. The fix is not committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `project.annual_employee_cost / project.business_year_hours`. If either value is `NULL` in the database, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's `calculate_cases_response_cost` (`case_cost/scheduled.py:63`) catches the error per case, so the case is skipped and its cost is never written. The log shows 708 of these between Sep 8 and Sep 14. The first is at 2025-09-08 15:55. The `scheduler.log` I searched does not show which project each case belongs to.

**Fix:**
- `src/dispatch/project/models.py`: adds `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. These are the model's existing column and schema defaults, and the column and schema defaults now reference the constants, so the values live in one place.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses the defaults when either value is `None`.

**Test:** `test_get_hourly_rate_falls_back_to_project_defaults` in `tests/case_cost/test_case_cost_service.py`, parametrised over three cases: both values missing, only cost missing, only hours missing. Each asserts the rate matches the model defaults. Without the fallback the test would hit the same `None / int` error. I did not run it against the unfixed code to see it fail.

**Test results:**
- `python -m pytest tests/case_cost tests/incident_cost tests/project`: 44 passed.
- Full `python -m pytest`: 363 passed, 4 skipped, 8 failed. The 8 failures are the same ones that fail on an unmodified `main`, in `tests/ai`, `tests/database` and `tests/entity`.

**Decisions and things to check:**
- I treated only `None` as missing. A stored `0` for business year hours would still raise `ZeroDivisionError`. I left that alone because the request was about missing values.
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` division with no fallback, so incident costs will hit the same error for projects with missing values. I did not change it because you asked about the case cost job. Say if you want it fixed the same way.
- The migration `2021-10-28_f95247c63eda` backfills `650000`/`2000` (or the `ANNUAL_COST_EMPLOYEE`/`BUSINESS_HOURS_YEAR` environment values) for projects that existed then. That is different from the model default. Projects created after that migration get `50000`/`2080`. Projects with missing values are therefore probably ones created outside the normal path. I used the model default as you asked, but finance may want to know the rate used for those projects is lower than the migration default.

----- next turn -----

Case 5356 grows steadily all week, so it is ordinary accrual, not an inflated jump. The first inflated change in the sync log is case 5284 on Sep 3. Here is the recap.

**Recap: Case response costs inflated after the Sep 2 deploy**

- **Symptom:** Stable cases had their classic response costs jump several times over in a single hourly sync, for example case 5363 from 2261 to 6241 on Sep 9. The jump came after the case was marked stable, and finance's warehouse received the inflated figures.
- **Cause:** On Sep 2, commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The timestamps are a case's `stable_at`, `escalated_at` and `closed_at`, and the minimum is the cut-off that stops accrual. The change moved the cut-off to the latest of them. A case escalated and then marked stable therefore kept accruing for the whole interval between escalation and stable. The June change that introduced the list (`200cd428`, #6074) used `min` deliberately.
- **Deploy:** `main-65f7df6e` rolled out to dispatch-web and dispatch-scheduler on Sep 2 at 18:14–18:15 UTC. It is the first image that contains `20f33137`.
- **First inflated cost:** case 5284, sync at 2025-09-03 11:20 UTC (3331 → 8804). The date comes from the finance sync log, not the Dispatch database, so it is what the sync recorded.
- **Fix:** `min` restored at `src/dispatch/case_cost/service.py:353`. Regression test `test_case_cost_stops_at_first_cut_off_timestamp` fails with `max` and passes with `min`.
- **Secondary bug:** the hourly `TypeError` (708 occurrences from Sep 8 onward) came from `get_hourly_rate` dividing by a null `annual_employee_cost`. The case was skipped and its cost never written. It now falls back to the project model defaults (50000 and 2080). Test `test_get_hourly_rate_falls_back_to_project_defaults` covers it.
- **Test status:** the full suite has the same 8 failures as unmodified `main`, in `tests/ai`, `tests/database` and `tests/entity`. All other tests pass.
- **Not done:** nothing is committed. Finance's already-written inflated rows still need correcting. `incident_cost` has the same unguarded division and was left unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost