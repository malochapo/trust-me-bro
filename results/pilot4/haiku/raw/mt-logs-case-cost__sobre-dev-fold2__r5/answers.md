**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```python
participant_role_renounced_at = min(timestamps)   # before
participant_role_renounced_at = max(timestamps)   # after
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. The function is meant to stop billing a participant's role at the *earliest* of those, as its own comment says ("Determine the earliest relevant timestamp for cost calculation cut-off"). With `max`, the cut-off becomes the *latest* of them. For a case that was escalated and later marked stable, billing now runs until `stable_at` instead of stopping at `escalated_at`. That adds the whole escalated-to-stable window for every participant, which is why costs jump when a case goes stable.

**Deploy that shipped it:** the `registry.example.com/dispatch:main-65f7df6e` image. The events log shows it pulled at 2025-09-02 18:14:25Z. `20f33137` is an ancestor of `65f7df6e`. The previous image, `main-3e0445ff` (Aug 27), does not contain it. The next image, `main-51546e13` (Sep 4 16:52Z), also contains it.

**Evidence:**
- The jumps are concentrated in cases that become `Stable`. The cost-sync warnings flag five such cases, all after the deploy: 5284 (Sep 3, 3,331 → 8,804), 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9, 2,261 → 6,241), and 5406 (Sep 12). The first flag is Sep 3, the first day after the rollout.
- Aggregate classic deltas per day are roughly 1% of the base before and after the deploy. The change is in the per-case step jumps, not the hourly accrual.
- The test suite misses it. `tests/case_cost/test_case_cost_service.py` only sets `stable_at`, with no `escalated_at` or `closed_at`, so `min` and `max` return the same value there.

**Caveats:**
- I could not query the database, so I have not seen the `escalated_at` values for these cases. The mechanism is inferred from the code and the timing, not from the rows.
- Case 5363 also rose from 131 to 277 on Sep 4, while it was still open. That looks like normal hourly accrual for an active case, not the bug.

**Separate problem (not the cause of the inflation):** from Sep 8, `dispatch.case_cost.scheduled` fails with `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. It is raised in `get_hourly_rate` (`service.py:118`) when `project.annual_employee_cost` is `None`. The scheduler log has about 1,400 of these. It stops those cases from being recomputed in the scheduler, so it may leave some costs stale. It needs its own look.

**Suggested fix (not applied):** revert line 353 to `min(timestamps)`, add a test where `escalated_at` is earlier than `stable_at`, and then recompute the affected cases. The finance warehouse rows changed since Sep 2 18:14 will need to be restated after the fix ships.

No code was changed.

----- next turn -----

The cost cut-off is fixed and a regression test covers it. The new test fails with the bug and passes with the fix.

**The fix:** `src/dispatch/case_cost/service.py:353` goes back to `min(timestamps)`. The cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, as the function's comment describes.

**The regression test:** `test_get_participant_role_time_seconds_stops_at_first_stop_timestamp` in `tests/case_cost/test_case_cost_service.py`. An assignee is assigned 4 hours ago, the case is escalated 3 hours ago and marked stable 1 hour ago. The role should be billed for exactly 3600 seconds.
- With `max` (the bug), it returns 10800 seconds and the test fails.
- With `min` (the fix), it returns 3600 and passes.
- I checked both by temporarily reintroducing `max`, then restoring `min`.

**Test results:**
- `python -m pytest tests/case_cost`: 20 passed.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed.
- The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and got the same 8 failures on the original code, so they predate this fix and are unrelated to it. I did not investigate them.

I haven't committed anything. The diff is two files: one line in the service and the new test.

**Still open:**
- The warehouse rows that were inflated since the Sep 2 18:14 deploy need restating once this ships. Costs for active cases will correct on the next sync, but the stable cases that were flagged need a recompute.
- The separate `TypeError` in `dispatch.case_cost.scheduled` (projects with `annual_employee_cost` set to `None`, from Sep 8) is not addressed here.

----- next turn -----

The hourly case cost job's `TypeError` is fixed, and the cases with missing project settings now get a cost. Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no check. The traceback says `'NoneType' and 'int'`, so the failing project has `annual_employee_cost` NULL. The model's `Column(default=...)` only fills the value on insert, so rows that were created without it stay NULL. The error is raised inside `calculate_case_response_cost_new`, which runs before the classic model, so the classic cost for those cases was not updated either. That's why they kept their old values.

I did not identify which project or projects have the NULL. The scheduler log doesn't name them, and I can't query the database from here. A query for `project` rows where `annual_employee_cost IS NULL OR business_year_hours IS NULL` would settle it.

**Fix:**
- `src/dispatch/project/models.py`: the defaults `50000` and `2080` are now the constants `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and the Pydantic defaults both use them, so there's one source.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default when its value is `None`. I used `is None` rather than `or`, so an explicit `0` is kept and still behaves as it did before.

**Test:** `test_get_hourly_rate_uses_project_defaults_for_missing_values` in `tests/case_cost/test_case_cost_service.py`. It covers both values NULL, only the rate NULL, and only the hours NULL. The original code raises the same `TypeError` on the first case, so the test would have caught this. I didn't run it against the old code, since it imports the new constants.

**Results:**
- `python -m pytest tests/case_cost`: 21 passed.
- Full `python -m pytest`: 361 passed, 4 skipped, 8 failed. The 8 failures are the same ones from before (AI summaries, the restricted case filter, and entity lookup), which I confirmed on the original code earlier.

**Not changed:** `src/dispatch/incident_cost/service.py:131` has the same unguarded division, so incident costs for projects with NULL settings would fail the same way. Your request was for the case cost job, so I left it alone. It's a one-line change if you want it. `src/dispatch/individual/service.py:104-107` already fills these defaults in when reading a project, so that path is safe.

----- next turn -----

The flagged jump on case 5284 at the Sep 3 11:20 sync is the first clear inflation from a stable transition. Cases 5346 and 5349 were newly added cases accruing normally, so they don't count. Here is the recap.

**Recap**

- **Symptom:** After September 2, the finance warehouse received case response costs several times the previous hour's values for cases that had just been marked stable. Example: `dispatch-default-security-5363` went from $2,261 to $6,241 on Sep 9.
- **Root cause:** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function is meant to stop billing a participant's role at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, billing ran until the latest of them, so an escalated-then-stable case was billed for the whole escalated-to-stable window. The existing tests set only `stable_at`, so `min` and `max` gave the same result and the regression went unnoticed.
- **Deploy:** The `dispatch:main-65f7df6e` image rolled out on 2025-09-02 at 18:14 UTC, and it contains `20f33137`. The earlier image, `main-3e0445ff`, does not.
- **Fix:** `min` is restored, with a regression test that fails on `max` (3600 s expected, 10800 s returned). Separately, `get_hourly_rate` now falls back to the project model's defaults when `annual_employee_cost` or `business_year_hours` is NULL. That removes the scheduler `TypeError` from Sep 8 onward. A test covers it.
- **Open items:** Restate the warehouse rows affected since the Sep 2 deploy. Find out which projects have NULL settings. Consider the same guard for `incident_cost/service.py:131`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost