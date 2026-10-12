The root cause is commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2). It shipped in the `main-65f7df6e` deploy on Sep 2 at 18:14–18:15 UTC. I haven't changed any code.

**The change**

In `src/dispatch/case_cost/service.py:353`, `get_participant_role_time_seconds` changed from `min(timestamps)` to `max(timestamps)`. For any case not in new or triage, the cost cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at` in the original code. After the commit it is the latest of them. If a case was escalated and later marked stable, each participant role now accrues cost from the escalation up to the stable time. That is the jump the finance warehouse picked up.

**Why I believe it's this commit**

- **Timing.** `20f33137` is an ancestor of `65f7df6e` and is not in the Aug 27 deploy (`3e0445ff`). The first spike is at 2025-09-03 11:20 UTC, the first hourly sync after the Sep 2 rollout.
- **Shape.** Five Stable cases spike in a single sync, each at 2.5–3.7x, and then sit flat. Case 5363 was flat at 2,261 from Sep 5 16:20 until the Sep 9 12:20 sync, which moved it to 6,241 (+3,980 in one step). The affected cases are:
  - 5284, Sep 3: 3,331 → 8,804
  - 5327, Sep 5: 2,244 → 5,539
  - 5264, Sep 8: 3,285 → 11,987
  - 5363, Sep 9: 2,261 → 6,241
  - 5406, Sep 12: 1,975 → 4,945
- **Test gap.** `tests/case_cost/test_case_cost_service.py:358` only sets `stable_at`, so `min` and `max` give the same result there. Nothing covers a case with two cut-off timestamps, which is why CI passed.

**What I ruled out**

- **cost-sync 1.5.0.** It went live on Sep 1, two days before the first spike. The log shows the spikes in the values Dispatch's API returned, and the job only copies them.
- **`51546e13`** (Sep 4 deploy). Its cost-path changes are one relationship line on `Case` plus canvas code. The first spike predates it anyway.
- **`65f7df6e`.** Its changes are the case-filter UI and database filter, nothing in cost code.

**Caveats**

- The logs don't contain case timestamps, so I can't confirm 5363's history directly. The "marked stable on Sep 9" story only fits the code if it had been escalated earlier, which would explain the freeze since Sep 5. Check `stable_at`, `escalated_at` and `closed_at` for 5363 in the database to confirm.
- The commit title says "latest", so the change looks deliberate, and I can't tell from the repo whether Jordan Lee's intent was the cost-cut-off semantics. The original `min` looks like the right cut-off (stop charging once the case first stops being active), but please confirm that with them.
- The detector only flagged jumps of 1.5x or more with a delta over 300, so smaller affected cases may not appear.
- The sync also shows large drops in multiples of about 727.5 on active cases. That looks like the 8-hour-per-day cap in the same function, and it predates the spikes, so I've left it out of the root cause.

**Suggested next steps (not done)**

1. Revert the `max` to `min` in `case_cost/service.py`, and add a test with `escalated_at` earlier than `stable_at`.
2. Have finance recalculate the affected cases once the fix is deployed. The warehouse already holds the inflated values.

----- next turn -----

The fix is in and the regression test is added. The full suite has 360 passing and 8 failing, and those 8 also fail on the untouched code, so they predate this change. I haven't committed anything.

**Changes**

- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`. The cost cut-off for a case is again the earliest of `stable_at`, `escalated_at` and `closed_at`.
- `tests/case_cost/test_case_cost_service.py`: new test `test_case_cost_stops_at_first_escalated_or_stable_time`. It escalates a case two hours after the participant was assigned, marks it stable one hour ago, and expects the role's time to stop at the escalation (3,600 seconds). It also checks the spiked-case pattern: the stable time comes after the escalation.

**Verification**

- Before the fix, the new test failed as expected: it got 7,200 seconds, the stable-time cut-off, where it expects 3,600.
- After the fix, `tests/case_cost`, `tests/case_cost_type` and `tests/case` pass (40 tests).
- Full suite: 360 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and ran those same tests on the original code: the same 8 fail there.

**Next steps (not done)**

- Confirm the intended semantics with Jordan Lee, since the original commit title asked for "latest".
- Ask finance to recalculate the affected cases after the fix ships. The warehouse still holds the inflated values for 5284, 5327, 5264, 5363 and 5406, and possibly others below the detection threshold.
- The 8 pre-existing failures are unrelated to this change, but they should be looked at separately.

----- next turn -----

The TypeError is fixed, and cases in projects with missing values now get a cost using the project model defaults. I haven't committed anything.

**Cause**

`get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` with no check. When a project has either value NULL, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler logged 708 of these from Sep 8 15:55 onward, all from `case_cost.scheduled`. The model `default=` only applies at insert, so rows that are already NULL never get the default.

I haven't confirmed how these projects ended up NULL. The likely path is the project update endpoint: `ProjectBase` accepts `None`, and `project/service.py:update` uses `exclude_unset=True`, so an explicit `null` is written as NULL. The logs don't name the affected projects, so I haven't checked which ones they are.

**Fix**

- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`, used by the column defaults and `ProjectBase`.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to each constant independently when its value is None.

**Tests** (`tests/case_cost/test_case_cost_service.py`)

- `test_get_hourly_rate_uses_project_defaults_for_unset_values`: four parametrized cases covering both NULL, either NULL, and nothing NULL.
- `test_calculate_case_response_cost_new_with_unset_project_values`: runs the new-model cost path the scheduler was calling, with NULL fields on the project.

Without the fix, the four NULL cases fail. The one with nothing missing passes, as expected.

**Verification**

- `tests/case_cost`: 25 passed.
- Full suite: 365 passed, 4 skipped, 8 failed. The same 8 failures that existed before this change remain, in `tests/ai`, `tests/database` and `tests/entity`.
- `ruff check` and `ruff format --check` pass on the changed directories.

**Things to know**

- Projects with a missing value are now costed at the defaults ($50,000 a year over 2,080 hours, $25/hour). That is a silent substitution, so finance should know that those cases are now priced at the default rate, which may not be their real rate. The alternative is to set the values on those projects.
- `src/dispatch/incident_cost/service.py` has an identical `get_hourly_rate` with no fallback. The logs show no errors from it, but it would fail the same way on a project with NULL values. I left it unchanged because you asked about case costs. It's a two-line change if you want it.
- The `min` fix from earlier is still in place in the same file, and that work is unaffected by this change.

----- next turn -----

## Recap

**Inflated case costs.** Since Sep 3, five Stable cases have been charged 2.5–3.7x their previous cost in a single hourly sync. The affected cases are 5284, 5327, 5264, 5363 and 5406. The cause is commit `20f33137` (Jordan Lee, Sep 2), which changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` rather than the earliest, so a case escalated and later marked stable accrued cost up to the stable time. It shipped in the `main-65f7df6e` deploy, which rolled out Sep 2 at 18:14–18:15 UTC. The first affected sync was Sep 3 at 11:20 UTC. **Fixed:** the `min` is restored, and `tests/case_cost/test_case_cost_service.py` has a regression test that fails on the old code. I have not confirmed the case timestamps directly, since the logs don't contain them.

**Hourly TypeError.** Since Sep 8 at 15:55 UTC the cost job has logged 708 `TypeError`s. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no check, so a NULL value raised. **Fixed:** missing values now fall back to the project model defaults (50,000 and 2,080), with tests. Cases in those projects are now costed at $25/hour, which finance should check against their real rates. I have not confirmed how the NULLs were written. The likely path is a project update that sends an explicit `null`. The same `get_hourly_rate` exists unchanged in `incident_cost/service.py`.

Neither fix is deployed yet, and the warehouse still holds the inflated values, so the affected cases need recalculating after deploy.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost