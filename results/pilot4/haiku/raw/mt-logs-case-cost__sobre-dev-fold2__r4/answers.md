**Root cause:** commit `20f33137` (“fix(case_cost): use the latest status timestamp as the cost cut-off”, Jordan Lee, Sep 2) changed `min` to `max` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). That moved the cost cut-off for every non-new/triage case from the earliest status change to the latest one.

**Shipped by:** deploy `registry.example.com/dispatch:main-65f7df6e` on **2025-09-02 18:14 UTC** (11:14 PDT). `20f33137` is an ancestor of `65f7df6e`, which is the tagged commit. The `dispatch-web` and `dispatch-scheduler` rollouts both happened in `events.log`, lines 2080–2098.

**Why it inflates costs:**
- The function's own comment still says it computes "the earliest relevant timestamp for cost calculation cut-off", so the code now contradicts its documentation.
- Before the change, a Stable case's cut-off was `min(stable_at, escalated_at, closed_at)`. After it, the cut-off is `max(...)`. For a Stable case with no `closed_at`, that is `stable_at`, usually later than `escalated_at`.
- So nothing changes while a case is new or in triage. The cost jumps when the case turns Stable, and it jumps retroactively by the participants' hours between escalation and stable time.
- Case 5363 fits this. Its classic cost grew about 146 per hour on Sep 4 (131 → 277 → 422 → 568), which is normal for an active case. It went Stable on Sep 9, and the next sync jumped it from 2261 to 6241 in one step.

**Evidence the jumps line up with the deploy:**
- The first flagged jump is case 5284 on Sep 3 at 11:20 UTC, after the Sep 2 18:14 deploy.
- The other flags are cases 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12), all Stable. The log shows no flags before Sep 3.
- The later deploy `main-51546e13` (Sep 4 16:52 UTC) also contains the change, so it is not the origin.
- The cost-sync image moved from 1.4.2 to 1.5.0 on Sep 1, two days before the jumps. The timing does not fit it, but its source isn't in this repo, so I did not check it.

**Limits:**
- I can't query the database, so the "stable_at minus escalated_at" explanation for the size of each jump is inferred from the code and timing, not confirmed against case timestamps.
- The commit title says `max` was intended. Whether "latest status" is the correct cut-off is a product decision for the finance and cost-model owners. The inflated retroactive jumps contradict the function's documented behaviour, so a fix would most likely revert to `min` or move the cut-off decision to whoever owns the cost model.

No code was changed.

----- next turn -----

The fix is in and a regression test covers it. The new tests fail on the old code and pass with the fix.

**The fix** (`src/dispatch/case_cost/service.py:353`): I changed `max(timestamps)` back to `min(timestamps)`. The function's own comment says it uses "the earliest relevant timestamp" for the cut-off, and that matches the behaviour before Sep 2.

I chose `min` on that basis. The commit title `20f33137` says "use the latest status timestamp", so the author may have meant it. If the finance and cost-model owners want the latest timestamp after all, this is a product decision to make with them, not something I should settle. Reverting is the safe choice given the retroactive cost jumps.

**The regression tests** (`tests/case_cost/test_case_cost_service.py`, appended after the existing stable-time test):
- `test_participant_role_time_stops_at_first_status_change`: the case is escalated, then marked stable later. The expected time ends at `escalated_at`.
- `test_participant_role_time_stops_at_first_closed_status_change`: the case is closed, then marked stable later. The expected time ends at `closed_at`.

The existing tests only set one cut-off timestamp at a time, which is why none of them caught this. With the `max()` restored, both new tests fail (`assert 7200.0 == 3600`). With the fix, they pass.

**Test results** (`python -m pytest`):
- `tests/case_cost`: 21 passed (19 existing + 2 new).
- Full suite: 361 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran them on the original code with my changes stashed, and they fail there too, so they predate this change. I did not investigate them.

**Not done:**
- I did not commit or push. The diff is 2 files: the one-line fix and the test additions.
- The inflated costs already in the finance warehouse are not corrected by this change. The hourly sync will only recompute values for cases it reads again, so the affected cases (for example 5264, 5284, 5327, 5363 and 5406, all flagged in `cost-sync.log`) will need a backfill or rerun. I have not checked how the sync picks up changed cases.

----- next turn -----

The TypeError is fixed and covered by a test. The case cost job now gives a cost to projects with a missing annual employee cost or business year hours, using the project model defaults (50000 and 2080).

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` with no check. The scheduled job calls it for every case. When a project has either value NULL, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`, and that case is skipped on every run. The first one in `scheduler.log` is at 2025-09-08 15:55 UTC, and there are 708 in total.

Two things I could not pin down:
- **Which projects have NULLs.** The logs don't name the project or case. To find them, run `SELECT id, name FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL;` against the Dispatch database. Nothing in this repo sets those values to NULL, so the cause is in how those project rows were written.
- **The Sep 6 error.** There is an error at 03:54 on Sep 6, but it is a database connection outage (`Connection refused` to `dispatch-db`), not this bug.

**Fix** (`src/dispatch/case_cost/service.py`): I added `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`, which mirror the Column defaults in `src/dispatch/project/models.py`. `get_hourly_rate` uses each default only when the matching project value is `None`. I used `is None` on purpose, so a value of 0 is not replaced; a 0 still raises `ZeroDivisionError`, and I left that alone.

**Test** (`tests/case_cost/test_case_cost_service.py`): a parametrized test covers both values set, only the cost missing, only the hours missing, and both missing. It checks the resulting rate and that `calculate_case_response_cost_new` returns a value, which is the path that raised. On the original code, the three missing-value cases fail with the same TypeErrors as the logs. The fully set case passes on both.

**Test results:** the case_cost tests pass (25 passed). The full suite has 365 passed, 4 skipped and 8 failed. The same 8 failures occur on the original code, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`, so they are not caused by these changes.

**Not done:**
- `src/dispatch/incident_cost/service.py:131` has the same unchecked division. Incident costs would fail the same way for a project with NULLs. I did not change it, since you asked about case costs; say if you want it fixed too.
- I did not commit. The working tree has the earlier `min` fix plus this one, in the same two files.
- The test file changed on disk during this session. I checked its current state, and it contains my changes. I have not reverted anything.

----- next turn -----

Here's the recap for the incident report.

**Summary**

- **Symptom:** case response costs for Stable cases jumped several times over in one sync, for example dispatch-default-security-5363 went from $2,261 to $6,241 on Sep 9. Nothing in the rates or cost models changed.
- **Root cause:** commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For a case past triage, the cost cut-off moved from the first status change (escalated, stable or closed) to the last. When a case turned Stable, every participant's hours were counted up to `stable_at`, so the cost jumped at that point. Active cases were unaffected, so costs only inflated once a case went Stable.
- **Deploy:** `main-65f7df6e`, rolled out to dispatch-web and dispatch-scheduler on Sep 2 at 18:14 UTC. `main-51546e13` on Sep 4 also contains the change but did not introduce it.
- **Fix:** restored `min(timestamps)`. Added two regression tests in `tests/case_cost/test_case_cost_service.py`; both fail on the buggy code (7200 s instead of 3600 s) and pass with the fix.
- **Separate issue:** the hourly case cost job logged a TypeError for 708 cases from Sep 8. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for NULL. A project with either value NULL raised an error, and the case was skipped every hour. Fix: fall back to the project model defaults (50000 and 2080). Added a parametrized test, which fails on the old code for the three missing-value cases.
- **Not yet resolved:**
  - Affected cases already in the finance warehouse still need a backfill or rerun.
  - The projects with NULL settings are not identified in the logs; use the query in my earlier note to find them.
  - `incident_cost/service.py` has the same unchecked division, so incident costs can fail the same way. Not changed.
  - Full suite: 8 failures on the original code too, in AI, database and entity tests.
  - Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours