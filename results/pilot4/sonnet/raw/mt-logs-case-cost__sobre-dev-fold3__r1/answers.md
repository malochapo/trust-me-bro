The root cause is commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off". It reached production in the deploy of image `main-65f7df6e` on 2025-09-02 at about 18:14Z.

**The bug.** The commit changed one line in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`):

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

- **What the code does:** `timestamps` holds `stable_at`, `escalated_at` and `closed_at`. They set the cut-off after which a participant's role stops accruing cost. The comment above the line still says "earliest relevant timestamp", and the later check says the cut-off is "when the case was marked as stable or closed".
- **Why it overstates cost:** `max` takes the latest timestamp, not the earliest. If a case was marked stable and then escalated or closed, the cut-off moves later and the cost keeps accruing for the extra time. A case with only `stable_at` set gives the same answer under `min` and `max`, so only some cases are affected.
- **Why it hits finance:** the classic cost is recalculated hourly by `calculate_cases_response_cost` in the scheduler. Cases that had stopped growing jumped, and the warehouse job copies the new numbers faithfully.

**Evidence from the logs**
- **Frozen costs jump:** case 5284's cost sat frozen at 3331 from 2025-08-29 13:20. It jumped to 8804 (+164%) at 2025-09-03 11:20, the first flagged sync after the deploy.
- **Other flagged cases:** four more cases were flagged as Stable with jumps of +147% to +265%. They are 5327 (09-05), 5264 (09-08), 5363 (09-09, $2,261 to $6,241) and 5406 (09-12).
- **Nothing flagged before the deploy:** `costsync.checks` has no flagged jump before the deploy. In `cost-sync.log` the five flagged cases are the only warnings.

**The deploy.** In `events.log` the image rollouts were:

| Time (Z) | Image | Contains `20f33137`? |
|---|---|---|
| 08-27 17:03 | `main-3e0445ff` | No (commit dated 08-26) |
| **09-02 18:14** | **`main-65f7df6e`** | **Yes (the culprit)** |
| 09-04 16:52 | `main-51546e13` | Yes (it is a descendant) |

- **Why `main-65f7df6e`:** `20f33137` was committed on 09-02 at 09:29 PDT (16:29Z). `main-65f7df6e` is the first image built after it. Both the db-upgrade job and the new web and scheduler pods used it.
- **Why not the next deploy:** the 09-04 deploy only carried the Slack canvas change on top.
- **Scheduler restarts:** the scheduler was restarted on 09-02 18:15 (with `65f7df6e`), on 09-04 and on 09-10 03:12. Only the 09-02 restart is the cause.

**Ruled out**
- **Finance job version:** case-cost-sync moved from 1.4.2 to 1.5.0 on 2025-09-01 at 10:20Z. That is before the first jump, and its logs show nothing unusual.
- **Rates and cost models:** the repo has no changes to them in this window.
- **Pre-deploy log noise:** the "No case cost model found" lines in the scheduler log predate the problem.

**Caveats**
- I didn't pull the case rows. I haven't confirmed that each flagged case had both `stable_at` and a later `closed_at` or `escalated_at`.
- I can't explain why 5284's jump landed at 09-03 11:20 and not right after the deploy. Its status or timestamps may have changed that morning.
- Check these two points in the database before you fix it.

Every case that is Stable, escalated or closed and has more than one of these timestamps has probably been overstated since 2025-09-02 18:14Z. The warehouse values for those cases need recomputing after the fix. I haven't changed any code.

----- next turn -----

I fixed it by changing `max(timestamps)` back to `min(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). I haven't committed anything.

I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It covers a case that was stable two hours ago and then closed an hour ago. It also covers one that was stable and then escalated. In both, the participant's time must stop at `stable_at`.

With the fix, all 20 tests in `tests/case_cost` pass. With the fix stashed, the new test fails on the old code (`7200.0 == 3600.0`) and the other 19 pass. That is the overcount that reached the warehouse.

The existing test only set `stable_at`, which is why it never caught the change.

The fix only changes costs going forward. The scheduler recalculates costs hourly, so Dispatch will correct the affected cases after the next deploy. The finance warehouse still holds the inflated values from 2025-09-02 onward. Case-cost-sync only upserts rows whose cost changed, so those rows will correct themselves once Dispatch's numbers drop. The finance team may still want to check the rows for the five flagged cases and any case that is Stable, escalated or closed.

----- next turn -----

The TypeError is fixed. Cases in projects with a missing rate setting now get a cost, using the project model's default for whichever value is missing. I haven't committed anything.

**Cause.** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the column defaults (50000 and 2080) only apply on insert. A project with either value NULL therefore raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. `ProjectBase` also accepts `None` for both fields.

**What the logs show.**
- **Volume:** the log has 708 of these errors, and every traceback is the same one.
- **Where it breaks:** `calculate_case_response_cost_new` and `calculate_case_response_cost_classic` both call `get_hourly_rate`. Both models fail for the affected cases, and the case ends up with no cost update at all.
- **Source of the NULLs:** the logs don't name the project or case, so I can't tell you which project has NULL rates. The error only shows up from Sep 8 and I found no related code change in this repo. Something probably set the values to NULL on a project around then, for example a settings save. Check the `project` table for NULLs to find it.

**Fix.** `get_hourly_rate` now falls back to the `Project` model's own column defaults, read from the model and not hard-coded. It handles each value separately, so a project missing only one still uses its own value for the other.

**Tests.** I added two tests to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_rates_use_model_defaults` covers both values missing, and each one missing on its own.
- `test_update_case_response_cost__project_without_rates` runs a full cost update on a project with both values unset.

All 22 tests in `tests/case_cost` pass. With the source fix stashed, the two new tests fail on the old code (along with the earlier stable-time regression test, since the stash covers both fixes).

Incident costs have the identical unguarded division in `src/dispatch/incident_cost/service.py:133`. I left it alone since you asked about cases, but it will fail the same way for incidents in those projects. It's a small change if you want it.

----- next turn -----

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in the participant role time calculation.
  - The cut-off for a case's cost is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case marked stable and later escalated or closed kept accruing cost until the later timestamp.
- **Deploy:** it shipped in image `main-65f7df6e` on 2025-09-02 at about 18:14Z. The deploy before it, `main-3e0445ff`, predates the commit.
- **Effect:** five cases were flagged by finance's sync, with jumps of +147% to +265%.
  - They are 5284 (09-03), 5327 (09-05), 5264 (09-08), 5363 (09-09, $2,261 to $6,241) and 5406 (09-12).
  - Smaller inflations may exist that the sync didn't flag.
  - Any case that has more than one of the three timestamps has probably been overstated since the deploy.
- **Fix:** restored `min`. The regression test is `test_case_cost_stops_at_earliest_status_timestamp`. It fails on the old code and passes on the fix.
- **Not verified:** I didn't check the database rows. I haven't confirmed that the five flagged cases have the timestamp combinations I described. I also can't explain why 5284's jump landed on 09-03 11:20 and not right after the deploy.
- **Warehouse:** the fix only changes costs going forward. The warehouse values from 2025-09-02 onward are still inflated until the scheduler recalculates after the next deploy.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Both are nullable project columns, and a project with either one NULL raises `TypeError`. The log has 708 of these errors.
  - Both the new and classic cost models call it, so affected cases got no cost update.
  - The logs don't say which project has NULLs or why it started on Sep 8.
- **Fix:** it now falls back to the `Project` model's column defaults for whichever value is missing. Two new tests cover it.
- **Open item:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division and is unfixed.
- Both fixes are uncommitted. The 22 tests in `tests/case_cost` pass.

**FIRST_INFLATED caveat.** I used 2025-09-03, the first flagged jump in the sync log. The jumps are the only evidence I have, so an earlier unflagged inflation on 09-02 can't be ruled out.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours