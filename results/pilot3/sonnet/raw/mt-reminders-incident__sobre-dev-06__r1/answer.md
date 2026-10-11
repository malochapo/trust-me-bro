## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`. It compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check never matched and the weekly reminders were never sent. The daily triage reminder doesn't use that check, which is why it kept working.

**Deploy:** Image `main-81d8ae42` went to production on 2025-08-13 at 16:40Z, replacing `main-b05613b5` from 2025-07-30. It was the first release to include `c509d45e`.

**Impact:** Reminders were sent on Mondays 07-28, 08-04 and 08-11. Monday 2025-08-18 was the first Monday after the deploy, and the logs show the jobs ran but sent nothing. The logs end on 08-20, so later Mondays are not covered, but they were almost certainly missed too.

**Fix:** `_is_reminder_day()` now uses `weekday()`. I added `tests/case/test_case_scheduled.py`. It covers every weekday, and it checks both reminder jobs on Monday, Tuesday and Sunday. It fails on the old code. The fix is uncommitted and not deployed, so production is still affected until it ships.

**Separate issue:** `case_close_reminder` logged a `TypeError` every evening. It was `datetime.utcnow() - case.triage_at` with `triage_at` set to `None`. Only the transition into triage sets that field, so cases that never went through it were skipped silently. The job now counts from `created_at` when `triage_at` is missing. This predates the weekday bug, so it was not a cause of the missed reminders on or after 08-18. It is also fixed in my working tree only, with a test.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at