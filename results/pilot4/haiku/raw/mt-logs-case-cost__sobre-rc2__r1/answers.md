**Root cause:** commit `20f33137` (Jordan Lee, 2025-09-02, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one word in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```python
participant_role_renounced_at = max(timestamps)   # was min(timestamps)
```

The function collects the case's `stable_at`, `escalated_at` and `closed_at`, and uses that value as the point where each participant's role time stops accruing. With `min`, the earliest of those timestamps is the cut-off. With `max`, the latest one is. For a case that was escalated and later marked stable or closed, participant time now accrues until the later event, so the classic cost jumps. The code comment directly above the change still says "Determine the earliest relevant timestamp", and the commit message contradicts it.

**Which deploy shipped it:** `65f7df6e` (2025-09-02). `20f33137` is an ancestor of `65f7df6e`, and it is not in `3e0445ff`, the image that was running before. The image `registry.example.com/dispatch:main-65f7df6e` was pulled by `dispatch-web` and `dispatch-scheduler` at 2025-09-02 18:14–18:15 UTC (events.log). The scheduler computes the case costs, so this is the deploy that changed the numbers. Later deploys (`main-51546e13`, 2025-09-04) carried the bug forward.

**Timing matches:** cost-sync raised no cost-jump warnings before the deploy. After it, the first jump was case 5284 on 09-03 (3331 → 8804), and there were four more on 09-05, 09-08, 09-09 (case 5363) and 09-12. All five are Stable cases.

**Limits of this evidence:**
- The logs don't include the timestamps for case 5363, so I haven't confirmed the exact mechanism for it. My reading is that it had an earlier `escalated_at` or `closed_at` than its `stable_at`, so the cut-off moved to the stable time when it was marked stable. That is consistent with the Sept 9 jump, but I haven't verified it against the database.
- The existing test `test_case_cost_stops_at_stable_time` (`tests/case_cost/test_case_cost_service.py:357`) only sets `stable_at`, so `min` and `max` give the same result there. That is why CI didn't catch it.
- I didn't run the test suite.

**Suggested fix (not applied, per your instruction):** revert line 353 to `min(timestamps)`, which matches the comment and the original design from `200cd428`. Add a test where `escalated_at` or `closed_at` is earlier than `stable_at`, and assert the cut-off is the earliest timestamp. Finance will also need to re-run the affected cases, since the warehouse rows for the flagged cases are overstated. I haven't checked which cases that covers beyond the five flagged.

----- next turn -----

The fix is in and the regression test is in place. The `case_cost` suite passes (20/20). I didn't commit anything.

**Changes**
- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`. The cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, which is what the existing comment says.
- `tests/case_cost/test_case_cost_service.py`: added `test_get_participant_role_time_seconds_stops_at_earliest_cut_off`. It sets an active assignee whose case was escalated two hours ago and marked stable one hour ago, then asserts the role time is the two hours up to escalation. The existing `stable_at`-only test couldn't catch this because it has only one timestamp.

**Verification**
- Before the fix, the new test fails: it returns 10800 s (3 hours, measured to stable) instead of 7200 s.
- After the fix, `python -m pytest tests/case_cost -q` gives 20 passed.

**Not done**
- I didn't run the full test suite, only `tests/case_cost`.
- Finance still needs to re-run the affected cases. The cost rows for the Stable cases flagged since 09-03 are overstated in the warehouse, and I haven't identified every affected case.

----- next turn -----

The hourly TypeError is fixed. Cases on projects with no annual employee cost or business year hours now get a cost, using the project model's defaults. The `tests/case_cost`, `tests/project` and `tests/individual_contact` suites pass (36 tests), and `tests/case_cost` passes again (25) after a later on-disk edit to the test file.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable. The model defaults (50000 and 2080) are applied only when a row is inserted, so a project whose values were later cleared (through the UI or the API) keeps `NULL`. The `TypeError` then fires on every hourly run. The logs contain 708 of these, all from this line, starting 2025-09-08 15:55. The logs don't name the project, so I can't tell which one was cleared or what changed on September 8.

**Changes:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic defaults use them, so the values can't drift apart.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants when a value is `None`. I also treat `business_year_hours = 0` as missing, because dividing by zero would fail the same way.
- `tests/case_cost/test_case_cost_service.py`: a parametrized `test_get_hourly_rate` covers both fields set, each one missing, both missing, and zero hours. I also added `import pytest` at the top of the file.

**Not changed, for you to decide:**
- `src/dispatch/incident_cost/service.py:133` has the same `get_hourly_rate` code. The incident job would hit the same error on any project with these fields cleared. I left it alone because you scoped this to the case job. It's a small follow-up.
- `src/dispatch/individual/service.py:104-107` hardcodes 50000 and 2080 instead of using the new constants. I didn't touch it.
- Finance may need a re-run for cases on the affected project. Those rows have been missing or stale since September 8.

----- next turn -----

Here is the recap for the incident report.

**Summary**

- **Inflated case costs:** Commit `20f33137` (2025-09-02) changed the cost cut-off in `get_participant_role_time_seconds` from `min` to `max` over `stable_at`, `escalated_at` and `closed_at`. Participant time then ran until the latest of those timestamps rather than the earliest, so Stable and closed cases were overcharged. It shipped in `main-65f7df6e`, which rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14 UTC. The first anomalous jump is case 5284 on 2025-09-03 at 11:20 UTC; I found no anomalous jumps in the earlier hourly runs. Case 5363 went from 2261 to 6241 on 2025-09-09. Five cases were flagged in total.
- **Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. A project whose `annual_employee_cost` was `NULL` raised a `TypeError` on each hourly run, starting 2025-09-08 15:55 UTC, so those cases got no cost. The logs don't name the project or show what cleared the value.
- **Fixes (uncommitted, in the working tree):**
  - Reverted `max` to `min` in `src/dispatch/case_cost/service.py`, with a regression test.
  - `get_hourly_rate` now falls back to the project model defaults (50000 and 2080, now named constants in `src/dispatch/project/models.py`) for missing values, with tests.
- **Not yet fixed:** `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` pattern. Finance also needs to re-run affected cases.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost