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