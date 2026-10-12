**Recap**

- **Symptom:** from mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, that compared `isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the helper never returned true. Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, skipped every send without logging an error.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13T16:40Z and contains the refactor. The previous image, `main-b05613b5`, predates it.
- **Evidence:** close reminders went out on Mondays 07-28, 08-04 and 08-11. On Monday 08-18, the first Monday after the deploy, none were sent.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. A new test checks the helper for each day of a week. It fails against the buggy code and passes with the fix.
- **Second issue (the nightly TypeError):** `case_close_reminder` subtracted `case.triage_at`, which is NULL for triage cases that never went through the triage status flow. The job logged the error and skipped those cases every evening. This predates the regression. It now counts from `created_at` when `triage_at` is missing, with two tests. I couldn't tell from the repo and logs which cases have the NULL, so that is still unchecked.
- **State:** both fixes and the new test file (`tests/case/test_case_scheduled.py`) are in the working tree, not committed. `tests/case` passes (24 tests). Reminders for 08-18 and any later Mondays were never sent, so those assignees weren't reminded and nothing has re-sent them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at