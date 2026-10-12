**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`:

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at` values. The code comment above it still says "Determine the **earliest** relevant timestamp for cost calculation cut-off". The change turns the cut-off into the latest of those timestamps. A case that was escalated or marked stable and later moved on now has its participants' time counted up to the last of those events, or up to now. Participant time drives the classic cost, so it is overstated.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z. I checked that `65f7df6e` contains `20f33137` and that the previous image `main-3e0445ff` (and `b01a1aba` before it) does not.
- The web and scheduler deployments both rolled to the new image in that window. The pods were `dispatch-web-zrhzjwmzrh` and `dispatch-scheduler-qdd74fpnsl`.
- That deploy also carried `5670487c`, `beb60cc4` and `65f7df6e`.
- The later image `main-51546e13` (2025-09-04 at 16:52Z) also contains the bug, but it didn't introduce it.

**Timeline match:**
- The first "flagged for review" warning in `cost-sync.log` is case 5284 on 2025-09-03 at 11:20Z (+164%). There were none before the deploy.
- More flags followed: 5327 on 09-05, 5264 on 09-08, 5363 on 09-09 and 5406 on 09-12. All were Stable cases.
- Case 5363 went from $2,261 to $6,241 on 09-09 at 12:20Z, which matches the example you gave.

**What I ruled out:**
- case-cost-sync was upgraded from 1.4.2 to 1.5.0 on 09-01 at 10:20Z, a day before the deploy. It reads the API and copies values, and no warnings appear until after the Dispatch deploy.
- Rates and cost models didn't change in the commit history for that window.

**Still unconfirmed:**
- I haven't worked out why 5363 dropped from 3425 to 1243 on 09-05, or why it sat flat at 2261 until 09-09. I'd guess status transitions plus the new `max` cut-off, but I haven't reproduced it.
- The logs don't include case timestamps, so I haven't verified per-case numbers.

**Things to know before fixing:**
- Reverting to `min` restores the old behavior. Whether `min` was right in every case is a separate question from the stable-then-closed intent the commit title suggests.
- The warehouse already holds inflated values for rows synced since 09-03. These should correct themselves on later syncs once the fix is deployed, but the finance team may need to confirm that.

I haven't changed any code.

----- next turn -----

I reverted the bug and added a regression test. All 20 tests in `tests/case_cost` pass, and I haven't committed anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `max(timestamps)` is back to `min(timestamps)`. The cost cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, which is what the code comment already says.
- **Test:** `test_case_cost_uses_earliest_status_timestamp_as_cut_off` in `tests/case_cost/test_case_cost_service.py` builds a stable case with `stable_at` earlier than `escalated_at` and `closed_at`. It asserts that the participant's time stops at `stable_at`. The existing stable-time test only set `stable_at`, which is why it didn't catch the `max` change.
- **Check that the test catches the bug:** with the source fix stashed (the `max` version), the new test fails by about 4 hours, and the other 19 pass.

Once this is deployed, the inflated warehouse rows should correct themselves on later hourly syncs. The finance team may want to confirm that for cases that are already stable or closed. Their cost values only change when the sync sees a different number from the API.

----- next turn -----

Status: the TypeError is fixed and tested. The case_cost tests pass, 21 of 21.

**Cause.** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Either column can be NULL in the database. The model's `default=` only applies when a row is inserted, so older rows or explicit `None` values stay NULL. The scheduler log shows the failure each hour: `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` in `get_hourly_rate`, reached from `calculate_case_response_cost_new` and `update_case_response_cost`. There are 728 of them in `scheduler.log`. `calculate_cases_response_cost` catches the error per case, so the other cases still get costs and the failing ones are skipped. Each of those cases never gets a cost update.

**Not found.** I couldn't tell from the logs why this started on 09-08, or which project has the NULLs, because the logs don't name the project. The cause itself is clear from the traceback.

**Fix.** When either value is `None`, `get_hourly_rate` now falls back to the `Project` model's column default. That is 50000 for annual cost and 2080 for business-year hours, and the code reads them from the column definitions instead of hardcoding them. A value that is set is used as is.

**Test.** `test_get_hourly_rate__missing_project_settings_use_model_defaults` covers both values missing, only the cost missing, and only the hours missing. I stashed my `src` changes and ran it against the old code, and it fails there.

`incident_cost/service.py:133` has the same unguarded division. I left it alone because you only asked about cases. Say if you want it fixed too.

Nothing is committed. The working tree holds both fixes, the `min` revert and this one.

----- next turn -----

## Recap

**Cost inflation**
- Commit `20f33137` (Jordan Lee, 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). The cost cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` instead of the earliest.
- Image `main-65f7df6e` shipped it. The web and scheduler pods rolled to that image on 2025-09-02 at about 18:14–18:15Z. The previous image, `main-3e0445ff`, doesn't contain the commit. The later image `main-51546e13` (09-04) carries the bug too but didn't introduce it.
- case-cost-sync 1.5.0 was rolled out on 09-01 and isn't the cause.
- The first inflated case cost I can see in the cost-sync log is case 5284 on 2025-09-03 at 11:20Z, $3,331 to $8,804, flagged by the sync's own check. It is the only large positive jump between the deploy and that point, and it came after the deploy. Other flagged cases followed: 5327 (09-05), 5264 (09-08), 5363 (09-09) and 5406 (09-12).
- I can't rule out smaller inflation earlier on 09-02 or 09-03, because the logs don't carry case status or timestamps.
- Fix: back to `min`, plus the regression test `test_case_cost_uses_earliest_status_timestamp_as_cut_off`. It fails on the old code.

**Hourly TypeError**
- `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. The error text is `'NoneType' and 'int'`, so the `None` is the numerator, `annual_employee_cost`. The scheduler log shows 728 occurrences, starting 2025-09-08.
- The model's `default=` only applies on insert, so older rows can be NULL. I couldn't find which project is affected or why it started on 09-08, because the logs don't name the project.
- Fix: a missing value now falls back to the `Project` column default, which is 50000 for cost and 2080 for hours. The test is `test_get_hourly_rate__missing_project_settings_use_model_defaults`.
- The same unguarded division exists in `incident_cost/service.py:133`. I left it alone.

**Status:** both fixes and both tests are in the working tree, uncommitted. `tests/case_cost` passes, 21 of 21. Warehouse rows written since 09-03 should correct themselves on later syncs once the fix is deployed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost