**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, Sept 2, 2025), changed one line in `src/dispatch/case_cost/service.py:353` from `min(timestamps)` to `max(timestamps)`. That line sets the cut-off for participant-role time once a case has left New/Triage. Before the change, the cut-off was the earliest of stable/escalated/closed. Now it is the latest, so a case that was escalated and later marked Stable keeps charging every participant from escalation until the Stable time. Nothing is charged for that window before the change, so the cost jumps in one step when the case goes Stable.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, which contains `20f33137` (confirmed with `git merge-base --is-ancestor`). Kubernetes events show it rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14–18:15 UTC**. The scheduler runs the case-cost calculation (`dispatch.case_cost.scheduled`), so the inflated values come from there. The previous image, `main-3e0445ff`, was deployed on Aug 27 and does not include the commit.

**Evidence from the logs:**
- Hourly accrual for ordinary cases is unchanged across the deploy (per-run deltas of about 146–194 both before and after). The problem only appears on the step changes.
- The `costsync.checks` warnings fire only for cases that went Stable, and every one is after the deploy:
  - 5284, Sept 3: 3331 → 8804
  - 5327, Sept 5: 2244 → 5539
  - 5264, Sept 8: 3285 → 11987
  - 5363, Sept 9: 2261 → 6241
  - 5406, Sept 12: 1975 → 4945
- The one link I could not confirm from the logs is that 5363 was escalated before it went Stable. The logs contain no case status history, so that part is inferred from the code. Checking `escalated_at` for 5363 in Dispatch's database would confirm it, and the size of the jump should match the escalation-to-Stable window times the participants' rates.

**Suggested fix (not applied, per your request):** revert line 353 to `min(timestamps)`. The commit message says "latest", so it's worth asking Jordan what they intended before reverting. Whichever way it goes, add a regression test where a case is escalated and then marked Stable. The existing `test_case_cost_stops_at_stable_time` only covers a case with no escalation, so it would not catch this. I haven't run the test suite.

**Cleanup:** the cases already affected will need their finance costs recalculated after the fix ships, because the hourly job only upserts rows that change.

----- next turn -----

The cost cut-off is fixed and a regression test covers it. The test fails on the buggy code and passes with the fix. I haven't committed anything.

**The fix:** `src/dispatch/case_cost/service.py:353` is back to `min(timestamps)`. That makes a case stop accruing at its earliest of escalated/stable/closed time. I reverted to the original behavior without checking intent with Jordan Lee, as you asked.

**The regression test:** `test_case_cost_stops_at_first_escalated_or_stable_time` in `tests/case_cost/test_case_cost_service.py`. It creates a participant assigned 3 hours ago, a case escalated 2 hours ago, and a case marked stable 1 hour ago. It expects 3600 seconds (until escalation), not 7200 (until stable). The existing stable-time test never escalates the case, which is why it didn't catch this.
- With `max` restored, the new test fails with `assert 7200.0 == 3600`.
- With the fix, all 20 tests in `tests/case_cost/test_case_cost_service.py` pass.

**Full suite (`python -m pytest`):** 360 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those 8 on a clean HEAD with my changes stashed and they fail there too, so they predate this change. I didn't investigate them.

**Still to do (outside this repo):** the fix only stops new charges from accruing. The cases already overcharged (5284, 5264, 5363, 5327, 5406 and others that went Stable after the Sept 2 deploy) need their cost rows recalculated in the warehouse. The hourly job only upserts rows whose values change, so it won't correct them by itself.

----- next turn -----

The full suite is running in the background. I'll wait for it to finish before reporting.

The fix and tests are in place. The full suite is still running in the background, and I'll report the result when it finishes.

----- next turn -----

The hourly job's TypeError is fixed and covered by tests. The full suite has the same 8 pre-existing failures as before, so nothing new broke.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. When a project has either value NULL, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's `calculate_cases_response_cost` catches it, logs it, and skips the case. The log has 708 of these, and the first is at 2025-09-08 15:55. I didn't find out which projects have NULLs or why the values became NULL around Sept 8. The model's `default=` only applies on insert, so it doesn't fill existing NULL rows.

**Fix:** when either value is None, `get_hourly_rate` uses the defaults from the `Project` model's columns (50000 and 2080), so the cost is still calculated. The values are read from `Project.__table__` rather than copied, so the model stays the single source.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_falls_back_to_project_defaults` covers each value missing alone and both missing.
- `test_calculate_case_response_cost_classic_with_missing_project_settings` checks that a case in a project with both values missing still gets a cost.

Both fail on the old code and pass with the fix. The case cost file passes all 22 tests.

**Not fixed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division. It's the incident equivalent of this job, so it will raise the same error for a project with NULL values. You didn't ask for it, so I left it alone. Say if you want it fixed the same way.

The changes are uncommitted in the working tree, along with the earlier `min` fix.

----- next turn -----

## Recap

**Bug 1: inflated case costs.** `get_participant_role_time_seconds` picked the maximum of the stable, escalated and closed timestamps as the cut-off for participant time, instead of the minimum. When a case was escalated and later marked Stable, every participant was charged for the gap between the two. Commit `20f33137` (Sept 2, 2025) made that change. It shipped in `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC. The first inflated cost in the logs is case 5284, which jumped from 3331 to 8804 in the sync at 2025-09-03 11:20 UTC. Five cases were flagged after Stable transitions: 5284, 5327, 5264, 5363 and 5406. Fixed by reverting to `min()`, with a regression test. The affected cases still need recalculation in the warehouse, because the hourly job only upserts rows whose values change.

**Bug 2: hourly TypeError.** `get_hourly_rate` divided a NULL `annual_employee_cost` by `business_year_hours`. The scheduler logged 708 such errors, starting 2025-09-08 15:55, and skipped those cases. Fixed by falling back to the `Project` model's column defaults (50000 and 2080) when either value is NULL, with two regression tests. I did not establish why those project values became NULL around Sept 8.

**Verification:** the new tests fail on the old code. The full suite shows 362 passed and 8 failed, and the same 8 tests fail on clean HEAD (AI service, restricted case filter, entity service). All changes are uncommitted.

**Open items:** `incident_cost/service.py:133` has the same unguarded division, so incident costs for projects with NULL values will hit the same error. Not fixed; say if you want it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost