**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`:

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

The timestamps are `stable_at`, `escalated_at` and `closed_at`. The surrounding comment still says "Determine the *earliest* relevant timestamp for cost calculation cut-off", and the stable/closed logic is meant to stop the cost clock at the first status change. With `max`, a case that has several of these timestamps is now costed up to the latest one. Cases that were escalated and later marked stable, or stable and later closed, stop accruing at the later time instead.

That also fits the numbers. Each case's cost stays flat or grows slowly until the one hourly run that recalculates it with the new cut-off, and then jumps. For example, case 5363 went from 2261 to 6241 on 2025-09-09 at 12:20Z.

**Evidence**
- `cost-sync.log` has no flagged jumps before 2025-09-03. The first is case 5284 at 2025-09-03 11:20Z, from 3331 to 8804. The other flagged cases are all Stable, and the last flag in the log is case 5406 on 2025-09-12, from 1975 to 4945.
- The jumps come in single hourly steps, because the Dispatch scheduler recomputes each case's cost with the new cut-off only when that case is picked up.
- case-cost-sync is not the cause. It moved from 1.4.2 to 1.5.0 on 2025-09-01 10:20Z, before the first anomaly. It reads the same 200 cases, and the jumps appear in the Dispatch API values it copies.

**The deploy that shipped it:** `events.log` shows the following image rollouts.

| Time (UTC) | Image | Contains `20f33137`? |
|---|---|---|
| 2025-08-27 17:02 | `main-3e0445ff` | No, it predates the commit |
| 2025-09-02 18:14 | `main-65f7df6e` | Yes |
| 2025-09-04 16:52 | `main-51546e13` | Yes |

The `dispatch-db-upgrade-65f7df6e` job started on 2025-09-02 at 18:14Z. The scheduler was replaced at 18:15Z, and the web rollout finished at 18:15:54Z. `git merge-base --is-ancestor` confirms `20f33137` is an ancestor of `65f7df6e`, so that deploy is the first to ship it. The 09-04 deploy only carried it forward.

**Fix, to apply when you're ready:** revert `max` back to `min`. After that, the stable, escalated and closed cases whose costs were recalculated since 2025-09-02 18:15Z need their costs recomputed. The warehouse rows written since then also need correcting, because the scheduler's "already updated after stable_at" skip may keep some wrong values from being refreshed. I haven't made any changes.

----- next turn -----

I reverted `max(timestamps)` back to `min(timestamps)` in `get_participant_role_time_seconds()` (`src/dispatch/case_cost/service.py`). I also added a regression test, `test_participant_role_time_stops_at_earliest_status_timestamp`, in `tests/case_cost/test_case_cost_service.py`.

The test sets up a closed case with `escalated_at`, `stable_at` and `closed_at` at 6, 4 and 2 hours ago, and a role assumed 10 hours ago. It asserts that the role's time stops at the earliest timestamp. The existing stable test only set `stable_at`, which is why it never caught the change.

- **With the fix:** all 20 tests in `tests/case_cost` pass.
- **Without the fix:** the new test fails. I stashed the source change to check this and then restored it.

Nothing is committed. I haven't touched the data side. The cost rows recalculated since 2025-09-02 18:15Z, and the matching warehouse rows, still hold the inflated values. Once the fix is deployed, those cases need their costs recomputed, and the scheduler's "updated after stable_at" skip may leave some stale unless it is bypassed.

----- next turn -----

The TypeError is fixed, and the affected cases now get a cost. Tests in `tests/case_cost` pass (22) with the change, and the new tests fail without it.

**Cause:** the traceback runs through `calculate_cases_response_cost`, then `update_case_response_cost`, then `calculate_case_response_cost_new`, then `get_hourly_rate(case.project)`. It fails at `project.annual_employee_cost / project.business_year_hours` with `NoneType / int`. So at least one project has `annual_employee_cost` and/or `business_year_hours` set to NULL.

I couldn't tell from the logs or the code which project it is or why it started on September 8. The columns are nullable, and the API schema (`ProjectBase`) accepts `None` for both. The column `default=` only applies when no value is given at insert. An explicit `None`, for example from a project edit, is stored as NULL.

The job catches the exception per case, so the other cases kept updating. The affected cases just never got a cost row refreshed, which is why the error repeats every hour: 708 times in the log.

**Fix:** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` now falls back to the Project model's column defaults (50000 and 2080) for whichever value is missing. It reads them from the model rather than hardcoding the numbers.

**Tests:** I added two in `tests/case_cost/test_case_cost_service.py`.
- **Rate test:** `get_hourly_rate` is checked with both values set, both missing, and each one missing on its own.
- **Cost test:** the case cost calculation runs for a project with both values NULL and returns both the new and classic costs.

**Not done:**
- **Incident costs:** `incident_cost/service.py` has the same `get_hourly_rate` code and the same weakness. I left it alone because you asked about cases.
- **Underlying data:** I haven't fixed the NULL values on the project itself, and nothing stops the API from writing them again.

Nothing is committed.

----- next turn -----

## Recap

**Cost inflation**
- Cause: commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. This is the cut-off for when a participant's time stops counting. It should be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has more than one of these timestamps was costed up to the latest one.
- Deploy: the commit shipped with image `main-65f7df6e`. Its db-upgrade job started on 2025-09-02 at 18:14Z, and the scheduler and web rollouts finished by 18:15:54Z. The 09-04 deploy (`main-51546e13`) only carried it forward.
- First inflation: the first large jump in the cost-sync log is case 5284 on 2025-09-03 at 11:20Z, from 3331 to 8804. I scanned every sync between the deploy and that run and found no other jump above 300. Cost-sync 1.5.0 (2025-09-01) is not involved.
- Fix: `max` is reverted to `min`, with a regression test.
- Still to do: recompute the case costs updated since 2025-09-02 18:15Z, and correct the matching warehouse rows.

**Hourly TypeError**
- Cause: `get_hourly_rate()` computes `annual_employee_cost / business_year_hours`. The error text is `NoneType / int`, so the numerator was None, which means `annual_employee_cost` was NULL on at least one project. The earlier "and/or" in my last message was looser than the evidence allows. A NULL `business_year_hours` would also fail, but with a different message, and the logs show none.
- The columns are nullable and the API accepts `None`. The column default only applies when no value is given at insert, so an explicit `None` is stored as NULL.
- Fix: both settings now fall back to the Project model's defaults, with tests.
- Not found: why it started on 2025-09-08, and which project it is.
- Not fixed: `incident_cost/service.py` has the same weakness, and nothing stops the API from writing NULLs again.

Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost