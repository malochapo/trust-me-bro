**Recap**

- **Symptom:** Since mid-August, assignees stopped getting the weekly Monday reminders to close long-running triage and stable cases. Daily triage reminders kept working.
- **Root cause:** Commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both weekly reminders (close and stable) went silent. The daily triage reminder doesn't use the helper, so it was unaffected.
- **Deploy:** The commit reached production in image `registry.example.com/dispatch:main-81d8ae42`, deployed 2025-08-13 16:40Z. The deploy before it (`main-b05613b5`, 2025-07-30) doesn't contain the commit. Reminders were sent on 07-28, 08-04 and 08-11 and not on 08-18.
- **Fix:** The helper now uses `weekday() == calendar.MONDAY`. A regression test covers it, and the test fails on the old code.
- **Separate daily TypeError:** `case_close_reminder` logged an error every evening for triage cases whose `triage_at` was `None`. Only `case_triage_status_flow` sets that field. Some paths, such as the Slack handlers, set the status to triage directly. The job now counts from `triage_at`, or from `created_at` when `triage_at` is missing. A test covers it.
- **Left open:** The Slack handlers still don't set `triage_at`.
- **Not verified:** Whether the production build of `main-81d8ae42` was exactly that commit. I took the image tag at face value.
- **State:** The fixes and tests are in the working tree, uncommitted. I ran only `tests/case`, not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at