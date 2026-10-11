**Recap**

- **Symptom:** from mid-August, assignees stopped getting the Monday reminders to close their long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday test into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The helper therefore returned False every day, and `case_close_reminder` and `case_stable_reminder` never sent anything. `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders kept working.
- **Deploy:** the scheduler and API pods restarted on 2025-08-13 at about 16:40Z and moved from image `main-b05613b5` to `main-81d8ae42`. That image's commit was made after `c509d45e`, so it contains the refactor.
- **Log evidence:** the Mondays 07-28, 08-04 and 08-11 each logged 4 to 6 "Case close reminder sent" lines. Monday 08-18 logged none, only a triage reminder to one assignee.
- **Fix:** the helper now uses `weekday() == calendar.MONDAY`. The regression test pins Mondays to True and the other days to False, and it fails on the old code.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at` empty. The field is only set in `case_triage_status_flow`, so cases that reach triage another way never get it.
- **Fix:** the job now falls back to `created_at`, so those cases get their weekly reminder. Four tests cover this, and the new test file has 12 tests that all pass. This error was independent of the outage and dates from before it.
- **Status:** both fixes are in the working tree, uncommitted and not deployed. Reminders stay off in production until they ship.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at