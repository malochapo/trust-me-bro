**Root cause:** commit `20f33137` (Jordan Lee, Sep 2 2025, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`) from `min(timestamps)` to `max(timestamps)`. For cases past `new`/`triage`, the cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`. After the change it's the latest. Accrual now runs until the last milestone is set, so when a case moves from escalated to stable or closed, all the time in between is billed at once.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out on Sep 2 at 18:14–18:15 UTC. `20f33137` is an ancestor of `65f7df6e`. The db-upgrade job, `dispatch-web` and `dispatch-scheduler` all moved to that image in that window. The scheduler is what runs the cost recalculation, so that is where the change takes effect. The scheduler ran `65f7df6e` until Sep 4 16:53, then `51546e13`, which also contains the commit, so the behaviour persisted.

**Evidence:**
- **Timing:** no hourly cost step of 300 or more in the logs from Aug 25 to Sep 2, and the largest was 230. The first large jump came at Sep 3 11:20 (case 5284, 3331 → 8804). Later jumps: Sep 5 (+3295), Sep 8 (+8702), Sep 9 (+3980 for 5363), Sep 12 (+2970 for 5406).
- **Case 5363:** its value grew about 146 per hour from Sep 4, then stayed flat at 2261 from Sep 5 16:20 until Sep 9 11:20. At 12:20 on Sep 9, when it was marked Stable, it jumped to 6241. That is the pattern of a cut-off that froze at an earlier milestone and then moved to a later one. The logs don't record `escalated_at`/`stable_at`, so this is inferred, not confirmed.
- **Ruled out, cost-sync 1.5.0:** it started Sep 1 10:20 with no jump at the switch. Changed-case counts and the hourly delta distribution look the same before and after, so the job copies what Dispatch reports.

**Open points:**
- Case 5363 also dropped from 3425 to 1243 at Sep 5 09:20. Neither `min` nor `max` explains a decrease, so I haven't accounted for it.
- The commit title says "latest", which matches the diff. But the comment directly above the code says "earliest relevant timestamp for cost calculation cut-off", and the commit body is empty. Jordan should confirm the intent before anyone reverts it.
- The existing test `test_case_cost_stops_at_stable_time` only covers `stable_at` with no earlier milestone, so it doesn't catch this.
- Separately, since Sep 6–8 the scheduler has logged `unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate` (`service.py:118`), which means `project.annual_employee_cost` is `None` for some project. That likely stops cost recalculation for that project. It doesn't explain the jumps, but it's worth a look.
- The scheduler only recalculates a stable case if its stored cost was last updated before `stable_at`. Inflated values won't correct themselves, so they'll need recalculating once the code is fixed.

I haven't changed any code. Next step, if you agree: confirm the intent with Jordan, and if `min` was right, revert it and recompute the affected cases in the finance warehouse.

----- next turn -----

The fix is in, with a regression test. The case cost tests all pass (20/20), and the full suite has 8 failures that also occur on the untouched tree.

**The fix:** `src/dispatch/case_cost/service.py:353` now uses `min(timestamps)` again, so a case's billable time ends at its earliest milestone (escalated, stable or closed). That matches the code comment above it. The commit title said "latest", which is the opposite; I went with the comment since it describes the original design and the commit gave no reason. If Jordan had a specific case in mind when he made the change, that's worth checking.

**The regression test:** `test_get_participant_role_time_seconds_stops_at_first_milestone` in `tests/case_cost/test_case_cost_service.py`. It sets a participant assumed 3 hours ago, a case escalated 2 hours ago and stable 1 hour ago, then expects 3600 seconds. On the old `max` code it fails with `7200.0 == 3600`; with the fix it passes.

**Full suite:** 360 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (5), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). The same 8 fail with my changes stashed, so they predate this work and I haven't looked into them.

**Not done:**
- I haven't committed anything.
- The cost values already inflated in the finance warehouse are still wrong. The scheduler only recalculates a stable case when its stored cost predates `stable_at`, so those rows won't correct themselves. They need a recalculation or a manual correction, which I'd want you to decide on.
- The scheduler's `unsupported operand type(s) for /: 'NoneType' and 'int'` errors (from `get_hourly_rate` when `annual_employee_cost` is `None`) are a separate issue. I left them alone.

----- next turn -----

The scheduler's `TypeError` is fixed: a project with no annual employee cost or no business year hours now uses the model defaults (50,000 and 2,080) and still gets a cost. I added a test for it, and the suite is at 361 passed with the same 8 failures as before.

**What causes it:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. For a few projects one of those is `NULL`, so every case in them raises `TypeError` each hour. The scheduler catches the exception per case, so the other cases still update. The project schema accepts `None` for both fields, and the update path uses `exclude_unset=True`, so an explicit `null` written through the API or UI stores NULL. I can't tell from the logs which write nulled these particular projects, so that link is an inference.

**The change:**
- `src/dispatch/project/models.py`: the two defaults are now module constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the schema defaults use them, so they can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes the defaults when either value is `None`. It only handles `None`; a stored `0` for business hours would still raise `ZeroDivisionError`.
- `tests/case_cost/test_case_cost_service.py`: `test_get_hourly_rate_falls_back_to_project_defaults` covers both values unset, only cost unset, and only hours unset.

**Not verified:** I didn't run the new test against the old code, so I haven't seen it fail there.

**Left alone:**
- `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` and will hit the same error for those projects. I didn't change it because you scoped this to the case cost job, but it's a one-line-for-line copy of this fix if you want it.
- `individual/service.py` hard-codes the same two fallback values. I left it as is.
- I haven't committed anything. The rows that were already skipped for these projects will need their costs recalculated once this ships.

----- next turn -----

**Recap**

- **Cost inflation:** Commit `20f33137` (Sep 2) changed the cut-off in `get_participant_role_time_seconds` from the earliest milestone (escalated, stable or closed) to the latest. Time between escalation and stable/closed was then billed at once when the later milestone was recorded. Case 5284 jumped from 3331 to 8804 on Sep 3, the first clear case. Case 5363 jumped from 2261 to 6241 when it was marked stable on Sep 9.
- **Deploy:** Image `main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on Sep 2 at 18:14–18:15 UTC. The scheduler runs the hourly cost job, so it's where the bug took effect. The scheduler was on that image until Sep 4.
- **Fix:** Reverted the cut-off to `min(timestamps)`, matching the code comment. Added `test_get_participant_role_time_seconds_stops_at_first_milestone`, which fails on the old code (7200 vs 3600 s) and passes on the fix.
- **TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with NULL `annual_employee_cost` raised on every hourly run from Sep 8. The fix falls back to the model defaults (50,000 and 2,080) and adds `test_get_hourly_rate_falls_back_to_project_defaults`. How those projects got NULL is not in the logs; an explicit null through the project update path is the likely route.
- **Tests:** 361 passed, 4 skipped, 8 failed. The 8 failures are in the AI, database and entity tests and also fail on the untouched tree.
- **Not done:**
  - Nothing is committed.
  - The `incident_cost` module has the same `get_hourly_rate` bug, which I haven't fixed.
  - Warehouse rows already inflated or skipped need recalculating.
  - `FIRST_INFLATED` is the first clearly inflated case I could find. The Sep 2 deltas were at most 230, roughly twice the typical hourly rate of 97, so I can't rule out a smaller inflation that day.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```