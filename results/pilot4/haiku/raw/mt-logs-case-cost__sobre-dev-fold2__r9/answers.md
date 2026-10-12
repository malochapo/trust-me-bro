**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`.

The function builds a cost cut-off from a case's `stable_at`, `escalated_at` and `closed_at`. The comment directly above it says "Determine the earliest relevant timestamp for cost calculation cut-off", so `min` was the intended behavior. With `max`, a case whose later timestamp falls after `stable_at` accrues participant time up to that later time. The cost then freezes at the inflated value.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, which contains `20f33137`. It rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14–18:15Z** (11:14 PT). The previous image, `main-3e0445ff`, was live from 2025-08-27 and does not contain `20f33137`.

**Evidence from the logs:**
- Across the whole log there are exactly five single-run jumps above +400: cases 5284, 5327, 5264, 5363 and 5406. All five come after the rollout, and the first is 2025-09-03 11:20Z.
- Each flagged case accrues about 146 per hour while active, then jumps once when it is in the Stable state, and then stops changing. That fits a single recomputation with a later cut-off, and the scheduler's `updated_at > stable_at` check then skips the case.
- Before the rollout, there are no comparable jumps.
- The example, 5363, went 2261 → 6241 at 2025-09-09 12:20Z.

**Ruled out (as far as the logs show):**
- **cost-sync 1.5.0** (rolled out 2025-09-01 10:20Z, before the bad deploy): cost-sync only copies the values Dispatch returns from its API. The hourly accrual rate is the same before and after 1.5.0, so it is unlikely to be the cause, though I did not compare the two versions' code.
- **`main-51546e13`** (2025-09-04): it deployed after the first jump, so it cannot be the first cause.

**Open points:**
- The logs do not contain per-case timestamps. The mechanism requires one of `escalated_at` or `closed_at` to be later than `stable_at` for these cases. I could not confirm that for any of the five, so a DB query on case 5363 would settle it.
- Case 5363 is flat from 2025-09-05 16:20Z to 2025-09-09 12:20Z, even though you said it was marked stable on Sept 9. Worth checking its status history.
- `tests/case_cost/test_case_cost_service.py:358` sets only `stable_at`, where `min` and `max` agree, so the suite passes with the bug. A test with a later `closed_at` or `escalated_at` would catch it. I did not run the tests.

I did not change any code.

----- next turn -----

The cost bug is fixed, and there is a regression test that fails on the buggy code and passes on the fix. I have not committed anything.

**The fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. The cut-off is the earliest of stable, escalated and closed. This is the behavior the function's own comment describes.

**The regression test:** `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp` in `tests/case_cost/test_case_cost_service.py`. It marks a case stable one hour ago and sets `escalated_at` and `closed_at` later. It asserts that the participant's time stops at the stable mark, so it expects 3600 seconds. I checked that it fails with `max` (1 failed) and passes with `min`.

**Test results** (`python -m pytest`, PostgreSQL running locally):
- `tests/case_cost`: 20 passed, including the new test.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai`, `tests/database` and `tests/entity`. I stashed my changes and ran the same 8 tests on the original code, and they fail there too, so they predate this change and are unrelated to it.

The diff against `main` is one line in the service and the new test. The test suite is what the team relies on for this path, so the new test should go in with the revert.

----- next turn -----

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no null check. For a project where either field is `NULL`, that raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The hourly job catches the exception per case and logs it, so that case gets no cost for that run. The scheduler log has 708 of these, all from `dispatch.case_cost.scheduled`. The first is at 2025-09-08 15:55Z.

**Fix:**
- `src/dispatch/project/models.py`: the defaults 50000 and 2080 are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and `ProjectBase` use them, so there is one source of truth.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default independently when its own value is `None`. A project missing only one value keeps the value it has.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, only the cost missing, and only the hours missing.
- `test_calculate_case_response_cost_without_project_hourly_inputs` runs the full case cost calculation for a project with both values missing and checks that the case gets a positive cost equal to the default-rate cost.

Both new tests fail on the original code and pass with the fix. The case-cost suite has 22 passing tests. In the full `python -m pytest` run, the only failures are the same 8 that were already failing before my changes, in `tests/ai`, `tests/database` and `tests/entity`.

**Not changed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division. The scheduler log has one `TypeError` from the incident cost job, on the same class of input, so incident cost has the same gap. I kept this change to the case cost job as you asked. It would be a small follow-up to apply the same fallback there.

----- next turn -----

## Recap

**Incident 1: inflated case response costs.** Since the 2025-09-02 deploy, the hourly case-cost sync has recorded sudden jumps in response cost for Stable cases. Each case's cost climbed normally while it was active, then jumped once when it reached Stable, and then stayed flat. Five cases were flagged: 5284, 5327, 5264, 5363 and 5406. Case 5363 went from $2,261 to $6,241 on 2025-09-09.

- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for a case's cost from its `stable_at`, `escalated_at` and `closed_at` timestamps. With `max`, a case whose escalation or closure time falls after its stable time keeps accruing cost up to that later time. The function's own comment specifies the earliest timestamp.
- **Shipped by:** image `main-65f7df6e` (which contains `20f33137`), rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14Z.
- **Fix:** restored `min`. Added `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp`, which fails with `max` and passes with `min`.

**Incident 2: hourly TypeError.** Since 2025-09-08 the case cost job has logged 708 `TypeError`s. Each one stops the cost update for one case in that run.

- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours` without a null check. A project with `annual_employee_cost` unset raises the error.
- **Fix:** a missing value now falls back to the project model default, 50000 for the annual employee cost and 2080 for the business year hours. The defaults are named constants in `project/models.py`, used by the column defaults and by the fallback. Added two tests: one for the rate fallback, and one for a full case cost calculation on a project with no hourly inputs. Both fail on the original code.

**Test results:** the case-cost suite passes (22 tests). The full suite shows 8 failures in `tests/ai`, `tests/database` and `tests/entity`, and the same 8 fail on the original code.

**Not committed:** all changes are in the working tree on `main`. Nothing has been pushed.

**Open items:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incident cost has one `TypeError` in the scheduler log, from the same kind of input. I did not change it.
- Case 5363's cost is flat from 2025-09-05 16:20Z to 2025-09-09 12:20Z, but it was reported as marked Stable on 09-09. The case's status history should confirm the timeline.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost