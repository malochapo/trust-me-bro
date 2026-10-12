**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, Sep 2 2025, 09:29 PDT). It is a one-word change in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`, from `min(timestamps)` to `max(timestamps)`.

**How the bug works.** For a case that isn't new or triage, the function builds a list of `stable_at`, `escalated_at` and `closed_at`. The code comment, "Determine the *earliest* relevant timestamp", says the earliest one is meant to end the participants' billable time.
- **Before the change:** the earliest timestamp won. Once a case was escalated, its cost stopped growing, and it stayed frozen at that point.
- **After the change:** the latest timestamp wins. An escalated case still freezes at `escalated_at` while that is its only timestamp. When someone later marks it stable (or closes it), the cut-off moves forward to that later time. The cost then bills all the time between escalation and the stable/close time in one step, instead of stopping at escalation.

**Evidence from the logs.**
- Case 5363 grew by about $145 an hour until Sep 5 16:20 ($2,261), then showed no change until Sep 9 12:20. On Sep 9 it jumped to $6,241, when it was marked stable.
- The sync flagged four other cases the same way: 5284 on Sep 3 ($3,331 to $8,804), 5327 on Sep 5 ($2,244 to $5,539), 5264 on Sep 8 ($3,285 to $11,987) and 5406 on Sep 12 ($1,975 to $4,945).
- All five flagged cases were in the Stable state, and no case was flagged before Sep 3.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z (11:14 PDT). In `events.log`, the `dispatch-db-upgrade-65f7df6e` job completed at 18:14:33Z. The web pods were then replaced, and the `dispatch-scheduler` pod was replaced at 18:15:09Z.
- `65f7df6e` is the commit right after the bad one in `main`, so its image is the first to include `20f33137`. The commits between them (`5670487c`, `beb60cc4`) don't touch cost code.
- The earlier deploy, `main-3e0445ff` on Aug 27, predates the commit.
- The later deploy, `main-51546e13` on Sep 4, also contains the bug but didn't introduce it.

**Caveats.**
- **Cost-sync upgrade:** `case-cost-sync` moved from 1.4.2 to 1.5.0 on Sep 1, a day before the Dispatch deploy. I can't see its code, and I'm not blaming it because no flagged jump predates the Sep 2 deploy. I haven't proved it innocent, though. If you can, check whether any case went stable between Sep 1 and Sep 2 without a jump.
- **Unexplained drop:** case 5363's cost also dropped from $3,425 to $1,243 on Sep 5 at 09:20 for a reason I didn't investigate. That's a separate oddity.
- **No effect on open cases:** the bug affects only cases that reach stable or closed after having been escalated. Cases that are still open are unaffected.

I haven't changed any code. The fix is presumably to revert to `min()`. The warehouse rows already written for the affected cases will also need correcting.

----- next turn -----

I reverted the bug and added a regression test. The `tests/case_cost` suite passes (20 tests), and I haven't committed anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `max(timestamps)` is back to `min(timestamps)`, so cost stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`.
  - **Cases covered:** a still-active participant on a case escalated 8 hours after they joined. One case is stable an hour ago and one is closed an hour ago.
  - **Assertion:** billed time must stop at `escalated_at`, not move on to the later stable or closed time.
  - **Check that it catches the bug:** with `max()` temporarily restored, the new test failed and the other 19 passed. I then put `min()` back.

The existing `test_case_cost_stops_at_stable_time` didn't catch the bug because it sets only `stable_at`, so `min` and `max` give the same answer.

The fix only stops new miscalculations. The inflated costs already in the finance warehouse (cases 5284, 5327, 5264, 5363 and 5406, and any others that went stable or closed after being escalated since Sep 2) need to be re-synced. Once the fix is deployed, the next hourly sync should do that, if the job recomputes from Dispatch's API.

----- next turn -----

The TypeError is fixed. Cases in projects with no annual employee cost or no business year hours now get a cost. All 21 tests in `tests/case_cost` pass.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both are nullable columns on `Project`, and the column defaults only apply to rows inserted through the ORM. A project with either value `NULL` therefore raised `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`, which the scheduler logged hourly. The traceback shows it coming from the new cost model (`calculate_case_response_cost_new`). The classic model calls the same function, so it was exposed to the same failure. There are 708 TypeError lines in `scheduler.log`, and the first is on Sep 8. I don't know why it began then. It could be a project edit that cleared the values, but the logs don't say.

**Fix:** a missing value now falls back to the `Project` model's column default (currently 50000 and 2080). Each value is handled on its own, so a project with only one set keeps it.

**Test:** `test_get_hourly_rate_uses_project_defaults_when_unset` covers both values missing, only the cost missing, and only the hours missing. With the source change stashed, the new test fails.

`src/dispatch/incident_cost/service.py:133` has the same unguarded division. I left it alone since you asked about cases, but it's the same one-line fix if you want it.

The affected cases will get a cost on the next hourly scheduler run after this is deployed. I haven't committed anything.

----- next turn -----

The first inflated case in the logs is case 5284, on 2025-09-03. The 5345 line the filter caught is ordinary hourly growth on a low base, not a jump.

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`, where `timestamps` holds `stable_at`, `escalated_at` and `closed_at`. The cost cut-off therefore moved from the earliest of those times to the latest.
- **Effect:** a case that was escalated froze its cost at `escalated_at`. When it was later marked stable or closed, the cut-off jumped forward and all the time in between was billed at once.
- **Deploy:** this reached production with the Sep 2 rollout of `registry.example.com/dispatch:main-65f7df6e` at about 18:14Z.
- **Evidence:** the sync flagged five cases, each in Stable state: 5284, 5327, 5264, 5363 and 5406. The first was 5284 on Sep 3 ($3,331 to $8,804).
- **Fix:** I restored `min()` and added `test_case_cost_stops_at_earliest_status_timestamp`. That test fails with `max()` and passes with `min()`. Warehouse rows already written for the affected cases still need a re-sync.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`, and both columns are nullable. The traceback says `NoneType / int`, so the left operand, `annual_employee_cost`, was the missing one. I couldn't see why it first appeared on Sep 8.
- **Fix:** a missing value now falls back to the `Project` model default, with a test, `test_get_hourly_rate_uses_project_defaults_when_unset`.
- **Same bug elsewhere:** `incident_cost/service.py` has the same unguarded division, and I didn't change it.

Both fixes are uncommitted, and the 21 tests in `tests/case_cost` pass.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost