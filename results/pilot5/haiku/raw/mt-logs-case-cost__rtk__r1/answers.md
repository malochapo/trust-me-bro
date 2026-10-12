**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). It replaced `min(timestamps)` with `max(timestamps)`. The `timestamps` list holds the case's `stable_at`, `escalated_at` and `closed_at`, and the cut-off for a participant's role time is now the latest of those instead of the earliest. The function's own comment still says "Determine the earliest relevant timestamp", and `min` was there since `200cd428` (adds stable status, June 2025). So a case's cost now keeps accruing until its latest milestone, which can be well after it was marked stable.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC (`events.log`). `65f7df6e` is a descendant of `20f33137` in the linear main history, so the fix went out with the dedicated-channel filter feature. The first anomalous jump is case 5284 on Sep 3 at 11:20, inside that window. The image was replaced by `main-51546e13` on Sep 4 at 16:52, which still contains the change, and the jumps continue through Sep 12.

**Why case 5363 matches:** the scheduler's `cost-sync` diffs show its cost growing about 145 per hour until Sep 5 at 16:20, then flat at 2261 for three days. That flattening is consistent with the case reaching a single milestone, `escalated_at`, where `min` and `max` agree. The Sep 9 jump to 6241 happens when `stable_at` is set. With `min`, the cut-off would have stayed at the earlier milestone and the cost would have remained 2261. The bug is therefore the `min` → `max` swap, not the rates or the cost models.

**Caveats:**
- The existing test `test_case_cost_stops_at_stable_time` (`tests/case_cost/test_case_cost_service.py:355`) only sets `stable_at`, so `min` and `max` give the same result and it would not catch this. I didn't run the test suite.
- Separate issue: the scheduler logs 709 `unsupported operand type(s) for /: 'NoneType' and 'int'` errors in `get_hourly_rate` (line 118), starting 2025-09-08 15:55. That points to a project with a missing `annual_employee_cost` or `business_year_hours`. It doesn't explain the inflation, but it means some cases are not getting costs computed at all.

No code was changed.

----- next turn -----

I fixed the cost calculation and added a regression test. The case-cost and incident-cost suites pass against the local PostgreSQL (35 tests).

**The fix** is in `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`. That matches the function's comment ("earliest relevant timestamp") and the original behavior from `200cd428`. I did not revert the rest of `20f33137`, which was a one-line change.

**The regression test** is `test_case_cost_stops_at_earliest_milestone` in `tests/case_cost/test_case_cost_service.py`. It sets up an assignee who joined 3 hours ago, a case escalated 2 hours ago, and a case marked stable 1 hour ago. The role time should stop at escalation, so 3600 seconds. I restored the `max` line temporarily and the test failed with `7200.0 == 3600`, so it catches this bug. I then put `min` back.

**Test environment:** `python -m pytest` in the existing `venv` failed to import `slack_sdk`, because that venv has no pip and its packages come from a shared scratchpad path with mismatched pytest versions. I did not change that venv. I created a clean one at `/tmp/sobre-bench-work/run-77806e94c2e0/test-venv` and installed `.[dev]` into it. pip needed `PIP_CERT=/etc/ssl/certs/ca-certificates.crt` because the sandbox has a TLS-intercepting proxy. I ran the tests with `test-venv/bin/python -m pytest`. You may want to rebuild the original venv or use this one.

Not done: I did not run the full suite, only the two cost test directories. I also did not touch the separate `'NoneType' and 'int'` errors in `get_hourly_rate`. That is still open, and it needs a look at which projects have missing `annual_employee_cost` or `business_year_hours`.

----- next turn -----

The scheduler's TypeError is fixed, and the cases now get a cost using the project model's defaults. The case-cost and incident-cost suites pass against PostgreSQL (38 tests).

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Those columns are nullable in the database. The model's `default=50000` and `default=2080` only apply when a row is inserted without a value, so a project with NULL in either column reaches the division as `None`. The `TypeError` is raised for each case on such a project, and the scheduler's per-case `except` logs it and moves on. That is why the same few cases fail every hour. The log shows the first occurrence on 2025-09-08 at 15:55. I did not query the database to see which projects have NULLs, so I can't name them.

**Fix:** `get_hourly_rate` now uses the column defaults when either value is `None`, read from `Project.__table__.c.<column>.default.arg`, so the 50000 and 2080 literals aren't duplicated. A value of 0 is still used as given, since only `None` triggers the fallback. The module now imports `Project` from `dispatch.project.models`.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate`: explicit values give the expected rate.
- `test_get_hourly_rate_uses_model_defaults_when_unset`: both NULL gives 25 (50000 / 2080, rounded up).
- `test_get_hourly_rate_uses_model_default_for_each_unset_value`: one NULL at a time (49 and 25).

I restored the original function temporarily, and the two NULL tests failed with the `TypeError`. I then put the fix back.

**Not done:**
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` with the same division. You asked about the case cost job, so I left it alone. It probably hits the same error for incidents on the same projects. I haven't checked the logs for that.
- The projects' NULL values themselves are unchanged. Those rows still don't have values, and the fix only makes the job tolerate them.

----- next turn -----

Here is the recap for the incident report. The six lines are at the end, in the requested form.

**What happened**
- Costs for stable cases roughly doubled or tripled starting Sept 3. Case 5363's classic cost went from 2261 to 6241 on Sept 9.
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Sept 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function's comment and the original code (`200cd428`) use the earliest milestone. With `max`, a case's role time runs until its latest milestone (stable, escalated or closed), not the earliest.
- That commit reached production in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on Sept 2 at 18:14–18:15 UTC. The image was replaced by `main-51546e13` on Sept 4 at 16:52, which still included the change.

**Fix 1 (cost inflation):** reverted `max` to `min` at `src/dispatch/case_cost/service.py:353`. Regression test `test_case_cost_stops_at_earliest_milestone` fails with `max` (7200 vs. 3600 seconds) and passes with `min`.

**Fix 2 (hourly TypeError):** `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours`. Projects with NULL in either column raised `TypeError` for every case on each hourly run. The scheduler caught it per case, so the rest of the run continued. The function now uses the project model's column defaults (50000 and 2080) when a value is `None`. Three tests cover this (`test_get_hourly_rate*`). The two NULL-case tests fail on the original code and pass with the fix.

**Verification:** `tests/case_cost` and `tests/incident_cost` pass against the local PostgreSQL (38 tests). I ran them in a clean venv I created at `run-77806e94c2e0/test-venv`, because the existing venv couldn't import `slack_sdk`.

**Caveats for the report**
- `FIRST_INFLATED` is based on the first large step change in `cost-sync.log` after the deploy, which is case 5284 on Sept 3 at 11:20 (3331 → 8804). Earlier diffs after the deploy are hourly growth on active cases, not step changes. A case that became stable or escalated in that window could be an earlier inflated one, but the logs don't show case timestamps to check.
- I don't know which projects have NULL values. The logs show only the error, not the project.
- `src/dispatch/incident_cost/service.py:131` has the same `get_hourly_rate` pattern and I didn't change it. I also haven't checked the logs for TypeErrors from the incident cost job.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost