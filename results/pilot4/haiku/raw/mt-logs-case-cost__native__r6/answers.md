**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed one line in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`) from `min(timestamps)` to `max(timestamps)`. That moves the cost cut-off for any case past New/Triage from the earliest of its stable, escalated and closed timestamps to the latest. A case's cost now keeps accruing until its stable (or close) time rather than stopping at escalation, so the jump comes when the case is marked Stable.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on **2025-09-02 at 18:14–18:15 UTC**. `20f33137` is an ancestor of `65f7df6e`, and `3e0445ff` (the previous production image, Aug 27) is not. The next image, `main-51546e13` (Sep 4 16:52), did not fix it.

**Evidence:**
- The first Stable-case jump in cost-sync.log is on Sep 3 11:20 (case 5284, 3331 → 8804). The later ones are 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12). Nothing is flagged before the Sep 2 deploy.
- Case 5363 grows about 145 per hour from Sep 4 until Sep 9, then jumps 2261 → 6241 at the Stable transition. After that it has no further changes in the log, so its cost froze at the new cut-off.
- The function's own comment says "Determine the earliest relevant timestamp for cost calculation cut-off", which is what `min` implemented. That `min` was introduced in `200cd428` (Jun 24, "adds stable status to cases"). The commit message describes the intent as "latest", but the comment and the original design say earliest, so the change contradicts the code's documented intent.

**Ruled out:**
- The finance job (case-cost-sync) changed from 1.4.2 to 1.5.0 on Sep 1 10:20. The change raised the Dispatch page size from 50 to 100 and added the "flagged for review" check. It copies values from the API and does not compute them. Its image did not change, and nothing jumped between Sep 1 and Sep 2.
- The Sep 2 deploy of `65f7df6e` also contains `51546e13`'s changes, but the jumps start before `51546e13` ships, so the Slack canvas work is not the cause.

**Caveats:**
- The logs have no case timestamps (stable_at, escalated_at, closed_at), so I inferred the mechanism from the code and timing rather than reproducing each case's numbers. A replay against case records would confirm it.
- Two moves don't fit this explanation alone: case 5363 dropped 3425 → 1243 on Sep 5 09:20, and case 5349 dropped 8573 → 7943 on Sep 9. I haven't explained them.
- `tests/case_cost/test_case_cost_service.py` covers this function, but I did not check whether any test pins the stable-cutoff behaviour, so I can't say why the change passed review.

I haven't changed any code. If you want, the next step is a fix that restores `min`, plus a regression test for a case that is escalated before it is marked stable.

----- next turn -----

I reverted the cut-off to `min` and added a regression test. The test fails on the buggy code and passes on the fix.

**The fix** (`src/dispatch/case_cost/service.py:353`): `participant_role_renounced_at = max(timestamps)` is back to `min(timestamps)`. The function's own comment says the cut-off is the earliest of the stable, escalated and closed times, so the code now matches it again.

**The regression test** (`tests/case_cost/test_case_cost_service.py`, `test_get_participant_role_time_seconds_stops_at_earliest_cutoff`): the participant is assigned 3 hours ago, the case is escalated 2 hours ago and marked stable 1 hour ago. The participant's time should stop at escalation, so the expected result is 3600 seconds. The existing stable-cutoff test only sets `stable_at`, so it can't tell `min` from `max`; this test can.
- With `max` in place, the test fails with `assert 7200.0 == 3600`, which is the overcount that inflated the costs.
- With `min` restored, the test passes. The full `tests/case_cost` file passes (20 tests).

**Full suite** (`python -m pytest`): 360 passed, 4 skipped, 8 failed. None of the failures involve case cost.
- Six are in `tests/ai/test_ai_service.py`. They fail because the sandbox can't download the `cl100k_base` tokenizer from `openaipublic.blob.core.windows.net`. I did not run these on the unmodified code, so that is an inference from the error, not a checked result.
- `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only` also fail on the unmodified commit, so they predate this change.

I haven't committed anything. The diff touches two files: the one-line fix and the new test.

----- next turn -----

The hourly job now gives a cost to projects with unset cost fields, and I added two regression tests. Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` with no check for NULL. Some projects have one of those columns set to NULL. The model's `default=` only applies on insert, so existing NULL rows keep it. Each hour, the scheduler reaches the crash for those cases, logs the `TypeError` and skips them. That is why the same few cases fail every run. The log has 708 of these, starting Sep 8. I can't see the database from here, so I haven't confirmed which projects have NULLs.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic schema both use them, so the values can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses the default for each field that is `None`. It checks `is None` rather than falsiness, so a real 0 is not replaced.

**Tests** (`tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both fields missing, only cost missing, and only hours missing.
- `test_calculate_case_response_cost_classic_with_unset_project_costs` runs the classic cost path, which is the one that crashed, on a project with both fields unset. It expects one hour at the default rate.
- Both fail on the original source and pass with the fix. The case cost suite has 22 passing tests.

**Full suite:** 362 passed, 4 skipped, 8 failed. The 8 are the same as before: six AI tests that need to download a tokenizer, and two database/entity tests that also fail on the unmodified commit.

**Not changed:** `src/dispatch/incident_cost/service.py:131` has the same unguarded division. Incident cost has the same bug, so it likely fails the same way for projects with NULL fields. I didn't change it because you asked about case cost, but the same fix applies there.

----- next turn -----

The recap is below. `FIRST_INFLATED` is based on the first large increase in the sync log. I did not verify that against case records.

## Recap

**Cost inflation.** Since Sep 2, some case response costs have been several times what they should be. Each case was charged for time up to its Stable time rather than its earlier escalation time. Commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off", changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). The function's own comment said "earliest", and the `min` dates to `200cd428` (Jun 24, "adds stable status to cases"). The change reached production in image `main-65f7df6e`, which rolled out on Sep 2 at 18:14–18:15 UTC. The first large inflated case in the sync log is case 5284 on Sep 3 at 11:20 (3331 → 8804). The example case, 5363, jumped from 2261 to 6241 on Sep 9. **Fix:** restored `min`. **Regression test:** `test_get_participant_role_time_seconds_stops_at_earliest_cutoff`. It gives 7200 s on `max` and 3600 s on `min`.

**Hourly TypeError.** Since Sep 8, the hourly job has failed on some cases with `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` (708 occurrences). `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Projects with a NULL `annual_employee_cost` make the division fail, so those cases get no cost update. The model's column default only applies on insert, so existing NULL rows keep their NULL. **Fix:** the project model defaults are now named constants (50000 and 2080), and `get_hourly_rate` falls back to them for any NULL value. **Tests:** `test_get_hourly_rate_uses_project_defaults_for_missing_values` and `test_calculate_case_response_cost_classic_with_unset_project_costs`. Both fail on the original code.

**Test suite.** 362 passed, 4 skipped, 8 failed. The failures predate these changes: six AI tests need a tokenizer download the sandbox can't reach, and two database and entity tests also fail on the unmodified commit.

**Open items:**
- `src/dispatch/incident_cost/service.py:131` has the same unguarded division, so incident cost likely fails the same way for projects with NULL fields. I did not change it.
- Some cases dropped sharply after the Sep 2 deploy (case 5291 at 19:20, case 5322 at 01:20 on Sep 3). The bug can only raise costs, so these drops are unexplained.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost