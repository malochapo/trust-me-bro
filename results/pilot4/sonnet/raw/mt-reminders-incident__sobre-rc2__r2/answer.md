**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving because that job has no weekday check.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) replaced the inline check `isoweekday() == 1` with a helper, `_is_reminder_day()`. The helper compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so it never returned true. Both `case_close_reminder` and `case_stable_reminder` call it, so neither job sent anything.
- **Deploy:** image `main-81d8ae42` went out at 2025-08-13T16:40Z and contains that commit. The previous image, `main-b05613b5`, did not, and it sent the reminders on 2025-08-04 and 2025-08-11. No close reminders appear in the logs on 2025-08-18, the first Monday after the deploy.
- **Fix:** `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`. A parametrized regression test covers Mondays, a Tuesday, a Wednesday and a Sunday.
- **Separate TypeError:** `case_close_reminder` logged `datetime - NoneType` every evening. Cases created directly in triage never get `triage_at`, because it is only set on status transitions. The job now counts from `triage_at or created_at`, so those cases get their weekly reminder. Three tests cover the change.
- **Caveats:** the fix needs a deploy to take effect, and the Mondays missed since 2025-08-18 are not backfilled. I ran only the new test file (8 tests, all passing), not the full suite, and `ruff` isn't installed here, so nothing was linted. Nothing is committed. `case_stable_reminder` still skips cases with no `stable_at` rather than falling back to `created_at`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at