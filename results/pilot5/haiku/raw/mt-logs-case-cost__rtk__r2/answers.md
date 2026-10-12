The root cause is commit `20f33137`, which shipped to production in image `main-65f7df6e` on Sep 2. It changed one `min` to `max` in the case cost cut-off. I haven't changed any code.

**Root cause**

`src/dispatch/case_cost/service.py:353`, in `get_participant_role_time_seconds`, now reads `max(timestamps)` where it used to read `min(timestamps)`. For cases past New/Triage, the timestamps are `stable_at`, `escalated_at` and `closed_at`, and they set the point where participant time stops accruing.

- Before: time stopped at the earliest of those, usually escalation.
- After: time stops at the latest, usually stable or closed.

For any case that was escalated and later marked Stable, every participant's hours now run from escalation until stable. The rates and cost models are unchanged, but the hours are not. A case with no timestamps still uses `now()`, which is why open cases grow every hour as designed.

**When it shipped**

- `main-3e0445ff` (Aug 27) does not contain the fix.
- `main-65f7df6e` contains it and was rolled out to `dispatch-web` at 2025-09-02 18:14:36Z and to `dispatch-scheduler` at 18:15:09Z (`events.log` around lines 2085–2111).
- `main-51546e13` (Sep 4) also contains it.

**Evidence from the logs**

Cost-sync's Stable-transition warnings start after the deploy, with none earlier in the logs:

| Case | Flagged | Classic cost |
|---|---|---|
| 5284 | Sep 3 11:20 | 3331 → 8804 |
| 5327 | Sep 5 16:20 | 2244 → 5539 |
| 5264 | Sep 8 10:20 | 3285 → 11987 |
| 5363 | Sep 9 12:20 | 2261 → 6241 |
| 5406 | Sep 12 11:20 | 1975 → 4945 |

**Ruled out**

- **cost-sync 1.5.0 (Sep 1 10:20):** the 1.5.0 run output has the same shape as 1.4.2. The job only copies values that Dispatch's API returns, and the jumps appear only after the Dispatch deploy.
- **Hourly growth on open cases:** this is by design, since the cut-off is `now()`. It also happened before Sep 2, so it's not the regression.

**Caveats**

- The commit title says "use the latest status timestamp", but the code's own comments say the opposite. The function still says "earliest relevant timestamp", and the renounced check says "before the case was marked as stable or closed". Both match `min`. So the change looks like a mistake, but the intended semantics are Jordan Lee's call to confirm.
- Closed cases are affected too (`closed_at` is in the same list), but cost-sync only flags Stable transitions, so closed-case impact is unverified.
- For case 5363 the warning's "previous" value (2261) matches the Sep 5 00:20 reading, not the last value before the jump. I didn't fully reconcile the hourly series between Sep 5 and Sep 9.

**Suggested next steps (for your go-ahead)**

1. Confirm the intended cut-off with Jordan Lee. If it's the earliest timestamp, revert `max` to `min`.
2. Find every Stable or closed case whose cost changed after Sep 2, and have finance re-sync them after the fix ships.

----- next turn -----

The fix is in and the regression test is in place. The case cost suite passes (20/20), and the new test fails on the buggy code. The full suite has 8 failures, and they fail the same way on the untouched code, so they are not from this change. I haven't committed anything.

**Changes**

- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`. The function's comments already describe the earliest-timestamp behaviour, so this brings the code back in line with them.
- `tests/case_cost/test_case_cost_service.py`: new test `test_case_cost_stops_at_first_stable_or_escalated_time`. It escalates a case, then marks it stable an hour later, and asserts participant time stops at escalation. Under `max` it fails with `10800.0 == 3600`.

**Test results**

- `tests/case_cost`: 20 passed.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 are `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail with my changes stashed, so they predate this fix and I didn't investigate them.

**How I ran the tests**

`python -m pytest` as specified did not work as-is in this sandbox:

- The venv was missing `slack_sdk` and other project dependencies.
- `pip install -e ".[dev]"` failed because PyPI's SSL certificate doesn't verify from here.

I ran the suite instead with `PYTHONPATH` pointing at a shim directory, `run-c62ae6cb804c/deps-shim`. It symlinks the pre-installed dependency set from `bench-venv/deps` minus pytest, so the venv's pytest (7.4.4) is used. The command was `PYTHONPATH=<shim>:$PWD/src python -m pytest`. I also ran `ensurepip` in the repo venv, which added pip to it. Neither the shim nor the venv change is in the repo. For a clean setup, rerun with network access and `pip install -e ".[dev]"`.

**Still open**

- The fix doesn't correct the cost values already written to the warehouse. Finance will need to re-sync affected Stable and closed cases since the Sep 2 deploy. The `closed_at` path was also affected and isn't covered by the logs I had.
- The 8 unrelated failures are worth a separate look.

----- next turn -----

Projects with a `NULL` annual employee cost or business year hours make the case cost job crash, and that is now fixed with the model defaults. I didn't find what wrote those `NULL`s on Sep 8.

**Cause**

`get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. When either is `NULL`, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The column defaults (50000 and 2080) only apply when a value is omitted on insert, so they don't cover an explicit `NULL`. The cases in those projects get no cost. The scheduler log has 708 `TypeError` lines from Sep 8 onward. I checked the first several, and they all match this traceback; I didn't check every one.

The logs don't name the projects, and no commit in the window touches these fields. So I can't tell what wrote the `NULL`s. To find the affected projects, run:

```sql
SELECT id, name FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL;
```

**Fix**

- `src/dispatch/project/models.py`: the defaults are now two constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic defaults use them, so they can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default when its value is `None`. Only `None` falls back, so a real `0` is still a value.

**Tests** (in `tests/case_cost/test_case_cost_service.py`)

- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, only hours missing, and only cost missing.
- `test_calculate_case_response_cost_with_missing_project_settings` runs a full classic cost calculation with both values missing, and expects one hour at the default rate, 25.

Both new tests fail when the fallback is disabled and pass with it.

**Results**

- `tests/case_cost`: 22 passed.
- Full suite: 362 passed, 4 skipped, 8 failed. The 8 are the same pre-existing failures as before.

**Not fixed: incident costs**

`src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incidents in those projects will hit the same `TypeError`. Applying the same fallback there is a small change, but it's outside what you asked, so I haven't made it.

**Environment**

As before, I ran tests with `PYTHONPATH` pointing at a shim of the pre-installed dependencies in `run-c62ae6cb804c/deps-shim`, because PyPI is unreachable from this sandbox. Nothing is committed.

----- next turn -----

Here is the recap for the incident report. The fixes are in the working tree and not yet committed or deployed.

**Incident recap**

- **Inflated costs:** after commit `20f33137` shipped on Sep 2 (image `main-65f7df6e`), participant time for cases that were escalated and later marked Stable ran until Stable instead of stopping at escalation. The cost-sync job flagged the first such case, 5284, on Sep 3 at 11:20 (3331 → 8804). The Stable jumps then continued (5327, 5264, 5363, 5406). Case 5363 went from 2261 to 6241 on Sep 9. The Sep 2 evening diffs for 5346 and 5349 are small, so I've treated Sep 3 as the first confirmed inflated cost, but I haven't ruled those two out.
- **Root cause:** `get_participant_role_time_seconds` used `max(timestamps)` where the earlier code used `min`. The code comments and the renounce check both describe the earliest-timestamp behaviour, so the commit title ("latest status timestamp") contradicts the code's intent. The fix restores `min`. A regression test covers an escalated-then-stable case, and it fails under `max`.
- **Ruled out:** the cost-sync 1.5.0 upgrade on Sep 1. Its log output is unchanged, and it only copies values from Dispatch.
- **Scheduler TypeError (from Sep 8):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Projects with a `NULL` annual employee cost raised `TypeError` on every hourly run, so their cases got no cost. Those cases now fall back to the model defaults of 50000 and 2080. The cause of the `NULL`s is unknown. The logs don't name the projects, and no commit in the window touches these fields. The SQL query to find affected projects is in the earlier summary.
- **Still open:** `incident_cost/service.py:133` has the same unguarded division, so incidents in those projects will fail the same way. The Sep 1 to Sep 14 warehouse values also need re-syncing after the fix ships.
- **Tests:** `tests/case_cost` passes (22). The full suite has 362 passed and 8 failed. Those 8 also fail without my changes, in `tests/ai`, `tests/database` and `tests/entity`.

```text
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```