Here is the recap for the incident report.

**What happened**
- **Symptom:** from early September the finance warehouse received classic case costs several times higher than the hour before. Case 5363 went from $2,261 to $6,241 on Sep 9 when it was marked stable.
- **Root cause:** commit `20f33137` (Sep 2, "use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Cost is meant to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, it kept accruing until the latest of them.
- **Deploy:** `main-65f7df6e` shipped it on Sep 2 at about 18:14–18:15Z. That is the first image that contains the commit, and the previous image `main-3e0445ff` doesn't. The later `main-51546e13` (Sep 4) also contains it.
- **First inflated case:** case 5284 jumped from 3331 to 8804 in the Sep 3 11:20Z sync, which was also the first `costsync.checks` warning. I checked for earlier unflagged upward jumps over $250 and found none between the deploy and that sync. The next jumps over $250 are Sep 5 (case 5327) and a batch of about $290 increases on Sep 6, which I treated as unrelated catch-up. The Sep 6 batch follows scheduler database connection failures around 03:00Z, but I didn't confirm that.
- **Ruled out:** case-cost-sync 1.5.0 (Sep 1) only changed the page size.
- **Fix:** reverted to `min`, with a regression test that sets all three timestamps. The earlier tests only set `stable_at`, which is why they missed it.
- **Second, unrelated bug:** from Sep 8 15:55Z the scheduler logged 708 hourly `TypeError`s (`None / int`). The cause was a project with `NULL` `annual_employee_cost`, which broke `get_hourly_rate`. It now falls back to the `Project` model defaults (50000 and 2080), with tests.

**Open items**
- **Warehouse backfill:** rows for cases that went stable, escalated or closed after Sep 2, 18:15Z are overstated. Rows for frozen cases won't self-correct once the fix ships.
- **Case 5363:** the Sep 5 drop from 3425 to 1243 is still unexplained.
- **Incident cost:** `incident_cost/service.py` has the same `get_hourly_rate` `NULL` bug, and I left it unfixed.
- **Project settings:** nothing yet stops a project update from writing `NULL` for these settings.
- **Not committed:** the fixes and tests are in the working tree only.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost