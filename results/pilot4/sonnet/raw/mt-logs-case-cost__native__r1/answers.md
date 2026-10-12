The root cause is commit `20f33137` (Jordan Lee, Sep 2), "fix(case_cost): use the latest status timestamp as the cost cut-off". It reached production in the deploy of `main-65f7df6e` on 2025-09-02 at about 18:14Z.

**The bug**

In `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`, around line 353), the commit changed `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. The comment above the code still says "earliest relevant timestamp", and the code after it still treats this as a cut-off. Rates and cost models were not touched.

Before the change, the cost stopped accruing at the earliest of those timestamps, normally `stable_at`. After it, the cost runs to the latest one. Any case that goes stable and is later closed now also bills the whole stable period. Participants who never renounced their role are billed for that time at the 8-hours-a-day rate.

**Evidence for case 5363 (`dispatch-default-security-5363`)**
- Its classic cost rose about $145 per hour until 2025-09-05 16:20Z, reaching $2,261, and then did not change at all.
- It stayed at $2,261 until 2025-09-09 12:20Z, when it jumped to $6,241. cost-sync's check flagged it with status Stable.
- I read the flat stretch as the case sitting in Stable, with the cost frozen at `stable_at`. The jump would then be the case being closed. `closed_at` becomes the maximum, so about 4 days of stable time were added.
- I inferred this from the cost pattern. The logs don't record the status changes themselves.
- The same pattern appears on the other flagged cases: 5284 on Sep 3, 5327 on Sep 5, 5264 on Sep 8 and 5406 on Sep 12. All were Stable when flagged, and the jumps ran from +147% to +265%.

**Deploy timeline from events.log**

| Deploy | Time | Contains `20f33137`? | Notes |
|---|---|---|---|
| `main-3e0445ff` | Aug 27, ~17:03Z | No (commit is from Aug 26) | The first web pod hit a registry 502 and ImagePullBackOff, but recovered on retry. |
| **`main-65f7df6e`** | **Sep 2, 18:14–18:15Z** | **Yes** | This is the first deploy with the bug. The db-upgrade job ran at 18:14, then web and the scheduler rolled out. |
| `main-51546e13` | Sep 4, ~16:53Z | Yes | An unrelated Slack canvas deploy that carried the bug forward. |

The first cost-sync run after the Sep 2 deploy was 18:20Z. The first flagged jump came on Sep 3, 11:20Z.

**Caveats**
- I matched the deploy by its image tag, which is the commit SHA. I did not find a log line showing the cost computation itself running on the new image.
- I haven't checked whether the scheduler or the API does the cost calculation. Both were on `65f7df6e` from Sep 2, so it doesn't change the conclusion.
- Costs already written for closed cases are probably inflated. The finance warehouse will keep those values unless they are recomputed or backfilled.

No code has been changed.

----- next turn -----

I reverted the cut-off to `min(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). The existing "earliest relevant timestamp" comment is accurate again. I haven't committed anything.

I added `test_case_cost_stops_at_earliest_status_time_when_closed_after_stable` to `tests/case_cost/test_case_cost_service.py`. It builds a case that went stable 4 days ago and was closed 1 hour ago, with a participant still in the role. It asserts the role time stops at `stable_at`, not `closed_at`.

With the fix, `python -m pytest tests/case_cost` passes (20 tests). With the old `max()` code and the new test in place, that test fails and the other 19 pass. The existing stable-time test didn't catch the bug because it never sets `closed_at`.

The fix only affects new calculations. Costs already in the database and in finance's warehouse for cases closed since the Sep 2 deploy, such as 5284, 5327, 5264, 5363 and 5406, stay inflated until they are recomputed or backfilled. Which cases are affected, and how to backfill them, is a decision for you and the finance team.

----- next turn -----

The TypeError is fixed, and cases in those projects now get a cost. I haven't committed anything.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. For some projects one of those is `NULL`, so the division raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The model's defaults of 50000 and 2080 only apply when a row is inserted, and the project schema allows `None`, so an update can leave either value unset. The first traceback in `scheduler.log` is on 2025-09-08 at 15:55, and there are 708 TypeErrors in total. The path is `calculate_cases_response_cost` → `update_case_response_cost` → `calculate_case_response_cost_new` → `get_hourly_rate`. The job catches the error per case, so only the cases in those projects are skipped each hour.

The logs don't show which project is affected or what unset its values on Sep 8. Check the project settings in Dispatch.

**Fix:** `get_hourly_rate` now uses the Project model's column defaults, read from the model rather than hardcoded, for whichever value is missing. A missing `business_year_hours` includes 0, which would otherwise divide by zero.

**Test:** `test_get_hourly_rate_falls_back_to_project_defaults` in `tests/case_cost/test_case_cost_service.py` covers both values unset, each one unset on its own, and both set. `python -m pytest tests/case_cost` passes (21 tests). With the `src` changes stashed, the new test fails.

`src/dispatch/incident_cost/service.py:133` has the same unguarded division. I left it alone because you asked about case costs. Say if you want the same fix there.

----- next turn -----

## Recap

**Cost inflation**
- Commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`.
- A case that went stable and was later closed was therefore billed for its whole stable period. Case 5363 went from $2,261 to $6,241 when it was closed on Sep 9.
- It shipped in the `main-65f7df6e` deploy on 2025-09-02 at about 18:14Z. The first inflated case I can see is 5284 on 2025-09-03. It went from $3,331 to $8,804 at the 11:20Z sync. Other cost drops after the deploy look like normal fluctuation, and I found no earlier inflated case.
- Fix: the cut-off is back to `min()`. The regression test `test_case_cost_stops_at_earliest_status_time_when_closed_after_stable` fails on the old code and passes on the fix.
- Costs already stored for cases closed since Sep 2 are still inflated and need a backfill. The affected cases include 5284, 5327, 5264, 5363 and 5406.

**Hourly TypeError (from Sep 8)**
- `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. For some project the first value was `NULL`: the error says `NoneType / int`, so the numerator was `None`.
- Fix: any missing value now falls back to the Project model's default (50000 or 2080). The new test is `test_get_hourly_rate_falls_back_to_project_defaults`.
- The same unguarded division still exists in `src/dispatch/incident_cost/service.py:133`.
- The logs don't show which project it is, so that is still to be found.

All 21 tests in `tests/case_cost` pass. Nothing is committed yet.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost