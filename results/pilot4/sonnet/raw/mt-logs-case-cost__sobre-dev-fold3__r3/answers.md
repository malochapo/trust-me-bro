**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, merged 2025-09-02 09:29 PDT). It changed one line in `get_participant_role_time_seconds`, in `src/dispatch/case_cost/service.py`:

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds whichever of `stable_at`, `escalated_at` and `closed_at` are set. The code comment still says "the earliest relevant timestamp". The cost of a participant who never renounced their role stops at that cut-off. Taking the latest timestamp instead of the earliest lets a case keep accruing cost past the point it was stabilised or escalated.

- **Why the jump is large:** Dispatch also applies a rule that cuts the time to a third after 24 hours. Cases with an earlier `escalated_at` or `closed_at` now get a longer cut-off, so their cost multiplies.
- **Why it shows up at "stable":** a case's cost is only capped once its status leaves new/triage. Case 5363 (dispatch-default-security-5363) was marked Stable on Sept 9. The 12:20 UTC sync that day shows classic cost 2261 → 6241 (+176%).
- **Scope:** only the participant-role time calculation is affected. Hourly rates and cost models are unchanged, which matches what you saw.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out to production on 2025-09-02 at about 18:14–18:15 UTC. The Kubernetes events show the `dispatch-db-upgrade` job, then the web pods, then the scheduler pod pulling it. That is the first deploy after `20f33137`, which sits just below `65f7df6e` in history. The previous image, `main-3e0445ff`, was deployed Aug 27 and predates the change.

The next deploy, `main-51546e13` on Sept 4, includes the change too. It is not the culprit, because the bug was already live. No rollback appears in the events through Sept 14.

**Timeline from the logs:**
- From Aug 25 to Sept 2, the cost-sync job flagged no cost jumps.
- `costsync.checks` warnings start on Sept 3 at 11:20 UTC, about 17 hours after the deploy.
- All five warnings are Stable cases, with increases of +147% to +265%:

| Time (UTC) | Case | Classic cost change |
|---|---|---|
| 09-03 11:20 | 5284 | 3331 → 8804 |
| 09-05 16:20 | 5327 | 2244 → 5539 |
| 09-08 10:20 | 5264 | 3285 → 11987 |
| 09-09 12:20 | 5363 | 2261 → 6241 |
| 09-12 11:20 | not looked up | not looked up |

I confirmed this from the log timing and the diff. I did not run the calculation on real case data, so I haven't checked that `escalated_at` or `closed_at` is later than `stable_at` on each flagged case.

**Separate issue:** from Sept 8 the scheduler logs `unsupported operand type(s) for /: 'NoneType' and 'int'` in `calculate_case_response_cost_new` (`case_cost/service.py`, line 466). It affects the new cost model on some cases and is unrelated to the cost jump. It's worth its own ticket.

**Next step:** revert `20f33137`, or restore `min`, and redeploy. Costs already written to the warehouse for cases that went Stable or were escalated since Sept 2 will need recalculating and re-syncing. I haven't changed any code, as you asked.

----- next turn -----

I've fixed the bug. In `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` uses `min(timestamps)` again as the cost cut-off, which restores the behaviour from before `20f33137`.

I also added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It covers two cases: stable two hours ago and closed one hour ago, and stable two hours ago and escalated one hour ago. In both, an active participant's time must stop at the stable timestamp.

`tests/case_cost` passes with the fix (20 passed). With only the fix stashed, the new test fails and the other 19 pass, so it would have caught this bug. The existing `test_case_cost_stops_at_stable_time` missed it because it only sets `stable_at`, so `min` and `max` gave the same result.

The changes are uncommitted. They still need a deploy, and costs already synced to the warehouse for cases that went Stable or were escalated since Sept 2 need recalculating and re-syncing. I haven't touched the separate `NoneType` error in `calculate_case_response_cost_new`.

----- next turn -----

The hourly case cost job's TypeError is fixed, and cases in projects without rate values now get a cost. `tests/case_cost` passes (22 tests). With only the source fix stashed, both new rate tests fail, so they would have caught this.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `project.annual_employee_cost / project.business_year_hours`. Both columns on `Project` are nullable. The column defaults (50000 and 2080) only apply when a row is inserted, so a project where either value is NULL hits `NoneType / int`.

The scheduler's `calculate_cases_response_cost` catches the exception per case. That is why only a few cases failed each hour, and why no cost was written for them. The traceback is in `calculate_case_response_cost_new`, which runs first, so the classic cost for those cases wasn't calculated either.

**Fix:** `get_hourly_rate` now falls back to `Project.annual_employee_cost.default.arg` and `Project.business_year_hours.default.arg` when a value is missing. Each value is handled on its own. The defaults are read from the model, so they aren't repeated in the cost code.

**Tests**, in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_values_use_defaults` covers both values missing, only one missing, and only the other missing.
- `test_update_case_response_cost__project_without_rate_values` runs the full new-model and classic calculation on a project with both values unset.

**Not determined:**
- **Why Sept 8:** the logs show the first error then, but I can't tell what put NULLs on a project. It was probably a project created or edited without those fields. Please check which project(s) have NULL values.
- **Incident costs:** `incident_cost/service.py` has an identical `get_hourly_rate` with the same weakness. I left it alone because you asked about cases. The same fix would apply there.
- **Recovery:** once deployed, the affected cases will pick up their costs on the next hourly run. Changes remain uncommitted.

----- next turn -----

## Recap

**Cost inflation:**
- Commit `20f33137` (merged Sept 2, 09:29 PDT) changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`.
- The cut-off is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, cases that were stable, escalated or closed kept accruing cost past that point.
- Image `main-65f7df6e` was the first production deploy after that commit. It rolled out on Sept 2 at about 18:14 UTC.
- The first inflated cost I found in the cost-sync log is case 5284 (dispatch-default-security-5284), at the 2025-09-03 11:20 UTC sync (3331 → 8804). I filtered the sync log for large single-sync jumps between the deploy and that sync and found only this one. I did not rule out smaller inflation in that window.
- The other flagged cases followed on Sept 5, 8, 9 and 12.
- Fix: `min` is restored, plus a regression test that sets `stable_at` together with a later `closed_at` or `escalated_at`.

**Hourly TypeError (since Sept 8):**
- `get_hourly_rate` in the same file divides `annual_employee_cost` by `business_year_hours`. Both are nullable project settings, and the model defaults only apply on insert.
- A project with a NULL value made the division fail with `NoneType / int`, and those cases got no cost.
- Fix: a missing value now falls back to the `Project` model default. Tests were added.
- The logs don't show what left the setting empty from Sept 8, so that is still open.
- `incident_cost/service.py` has the same unguarded `get_hourly_rate`. It is unchanged.

**Open items:** the code changes are uncommitted and not deployed. Warehouse costs for cases that went stable, escalated or closed since Sept 2 need recalculating and re-syncing.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours