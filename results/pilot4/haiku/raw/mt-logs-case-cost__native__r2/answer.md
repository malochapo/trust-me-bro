## Recap

**Cost bug:** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`, and the fix made it the latest. For a case escalated and later marked stable or closed, participant time kept accruing across the gap, and the cost jumped when the later event landed. Case 5363 is the example: flat at 2261 from Sep 5 to Sep 9, then 6241 when marked Stable.

**Deploy:** Image `main-65f7df6e` ran its database upgrade on Sep 2 at 18:14Z and replaced the scheduler pods at 18:15Z. That is the first deploy containing the commit.

**First inflated cost:** Case 5284 on Sep 3 at the 11:20Z sync, 3331 to 8804. It had been flat since Aug 29 and was marked Stable that day. I found no earlier inflation in the Sep 2–3 diffs. I haven't confirmed the stable timestamp from case data, since the logs don't include it.

**Fix:** The cut-off is back to `min`, with a regression test that fails under `max`. Full suite: the same 8 failures as before, none from this change.

**Second issue (TypeError):** 708 errors from Sep 8 to Sep 14 came from projects with `annual_employee_cost` set to NULL. The project edit form can clear that field, and the update writes the NULL. `get_hourly_rate` now falls back to the model defaults (50000 and 2080), with two tests. Projects that already have NULLs still have them in the database and need a data fix. The same division in `incident_cost` is unguarded and was not changed.

**Caveats:** The `FIRST_INFLATED` and deploy link rest on the cost-sync log. Nothing is committed.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```