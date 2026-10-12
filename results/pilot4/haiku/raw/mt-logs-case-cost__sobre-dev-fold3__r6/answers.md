**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed the cost cut-off from the earliest status timestamp to the latest. Cases that have more than one of stable/escalated/closed timestamps now accrue cost up to the latest one, so cost keeps growing after the case should have been frozen.

**Deploy that shipped it:** `65f7df6e` (feat(ui): filtering by dedicated channel cases). It contains `20f33137`, and the image `registry.example.com/dispatch:main-65f7df6e` rolled out to dispatch-web and dispatch-scheduler on **2025-09-02 at 18:14–18:15 UTC** (events.log). The scheduler computes these costs, so the change was live from that rollout.

**Evidence:**
- **Timing:** the first flagged case appears in cost-sync.log on **Sep 3 11:20 UTC**, about 17 hours after the rollout. Before that, no run flagged anything (`done: … 0 flagged`).
- **Flagged cases are all Stable:** 5284 (Sep 3), 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9). Each jumps in a single sync rather than drifting.
- **Case 5363 freezes, then jumps:** its classic cost is flat at 2261 from Sep 5 16:20 to Sep 9 12:20 with no diff lines. It then jumps to 6241 in the sync after it was marked stable. Under `min` the cut-off would stay at the earliest timestamp, so the value would not move. Under `max`, marking it stable makes `stable_at` the latest timestamp, which pushes the cut-off forward by the time between the earlier timestamp and the stable mark.
- **The code contradicts itself:** the function's own comment still reads "Determine the earliest relevant timestamp for cost calculation cut-off", and the renounced-at logic below it compares against "the case was marked as stable or closed".
- **Tests missed it:** `test_case_cost_stops_at_stable_time` (tests/case_cost/test_case_cost_service.py:355) only sets `stable_at`, with no escalated or closed timestamps, so `min` and `max` give the same result and the test passes either way.

**Not verified:**
- I could not query the Dispatch database, so the escalated/closed timestamps behind 5363 are inferred from the frozen-then-jump pattern, not read directly.
- The Sep 5 drop for 5363 (3425 → 1243) is not explained by this commit.
- I did not run the test suite.
- Commit `42699ebc` (flatten the restricted case filter) landed in the same window, but I found no cost-related path through it.

No code was changed.

----- next turn -----

The fix is in and the regression test is in place. Changes are uncommitted in the working tree.

**Fix** (`src/dispatch/case_cost/service.py:353`): the cost cut-off is back to `min(timestamps)`, the earliest of stable/escalated/closed. I changed `max` back to `min` rather than rewriting the logic. The function's own comment already said "earliest", and the logs show costs freezing at the earliest timestamp before the change.

**Regression test** (`tests/case_cost/test_case_cost_service.py`, `test_case_cost_cut_off_is_earliest_status_timestamp`): it sets up a case escalated 3h ago and marked stable 1h ago, then asserts the role's time stops at the escalation. The existing `test_case_cost_stops_at_stable_time` only sets `stable_at`, which is why it passed under `max`. I confirmed the new test fails on the buggy code and passes after the fix.

**Test results** (`python -m pytest`):
- `tests/case_cost`: 20 passed, including the new test (19 before).
- Other modules that touch cost or participant roles: 63 passed, 1 skipped.

**Decisions for you to confirm:**
- The commit title said "use the latest status timestamp", so the author may have intended `max`. I reverted it because the cost-sync data and the function's comment both point to the earliest timestamp, and finance's values were frozen under that behavior. If `max` was a deliberate product decision, this needs a different fix.
- I haven't corrected the already-inflated values in the warehouse. The cost-sync job upserts changed rows on each run, so the corrected values should flow through on the next runs, but I haven't verified that.
- I didn't deploy. The fix reaches production only after it is merged and released.

----- next turn -----

The hourly job's TypeError is fixed, and the cases now get a cost using the project model's defaults. Changes are uncommitted.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` directly. Some projects have a NULL in one of those columns, so the division raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler log has 708 of these from Sep 8 onward, each one costing the case that hour.

**Fix:**
- `src/dispatch/project/models.py`: the defaults 50000 and 2080 are now named constants `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults use them.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants when either field is None. Each missing field falls back independently.

**Tests** (`tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_falls_back_to_project_defaults` covers both fields missing, only the cost missing, and only the hours missing.
- `test_calculate_case_response_cost_with_missing_project_rate_fields` checks that the classic cost for one hour of assignee time with both fields missing equals the default hourly rate.

Both failed with the TypeError before the fix.

**Results** (`python -m pytest`):
- `tests/case_cost`, `tests/case`, `tests/project`, `tests/individual_contact`, `tests/api`, `tests/incident_cost`: 63 passed.
- `tests/case_cost`, `tests/incident_cost`, `tests/case_cost_type`, `tests/participant_role`, `tests/incident_role`: 51 passed.
- `ruff check` passes, and `ruff format` is clean on the changed files.

**Things to know:**
- **Why the fields are NULL is not established.** The column defaults only apply on insert, so rows that were already NULL stay NULL. I didn't find what cleared these values, or why it started around Sep 8. Someone should check the project rows and whether a recent change or migration nulls them.
- **Incident cost has the same bug.** `src/dispatch/incident_cost/service.py:131` has an identical `get_hourly_rate`. The incident-cost logs don't show these errors, but I didn't change it since you asked about the case job. It's a one-function fix if you want it.
- **Not verified:** I didn't check the warehouse for case costs that were skipped during the error window. The hourly job should recompute them on the next runs, but I haven't confirmed that.

----- next turn -----

Here is the recap for the incident report.

**Summary**

Since early September, case response costs for Stable cases were inflated. Costs kept accruing after the case should have frozen, so finance's warehouse received values several times too high. Separately, the hourly scheduler job logged a TypeError for some projects, so those cases got no cost.

**Cost inflation**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off became the latest of stable/escalated/closed instead of the earliest.
- A case escalated before it was marked stable kept accruing cost up to the stable time. Case 5363 was flat at 2261 from Sep 5 to Sep 9, then jumped to 6241 when it was marked stable.
- The commit reached production in image `main-65f7df6e`, which rolled out to dispatch-web and dispatch-scheduler on Sep 2 at 18:14–18:15 UTC.
- The first flagged inflation was case 5284 on Sep 3 at 11:20 UTC. The cost-sync log only flags large jumps, so smaller inflation before that can't be ruled out.
- Fix: restored `min`, which matches the function's own comment. Added `test_case_cost_cut_off_is_earliest_status_timestamp`, which fails on the buggy code.

**Hourly TypeError**
- `get_hourly_rate` in `src/dispatch/case_cost/service.py` divided `annual_employee_cost` by `business_year_hours` without checking for None. The scheduler logged 708 of these from Sep 8 onward.
- Fix: missing values fall back to the project model's defaults, now named constants in `src/dispatch/project/models.py`. Added two tests covering the fallback.
- Still open: what nulled these project fields is not established.

**Not verified or not done**
- Warehouse values for affected cases are not corrected. The hourly job should pick up the fixed values on later runs, but I haven't confirmed that.
- The fixes are uncommitted and not deployed.
- `incident_cost/service.py` has the same unguarded `get_hourly_rate`. The logs show no errors from it, and I didn't change it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost