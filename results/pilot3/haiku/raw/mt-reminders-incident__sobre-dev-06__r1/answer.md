Here is the recap for the incident report.

**Summary**

- **Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept arriving, and no settings changed.
- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0). The comparison was never true, so both the triage and stable close reminders were silently skipped every day.
- **Introduced:** commit `c509d45e` ("refactor(case): share the weekly reminder check"), which replaced the original, correct inline check with the helper.
- **Deployed:** the scheduler and web pods restarted on 2025-08-13 at about 16:40 UTC, running image `registry.example.com/dispatch:main-81d8ae42`. That image contains `c509d45e`. The previous image, `main-b05613b5`, does not. The logs show the Monday 2025-08-11 reminders were still sent under the previous image.
- **Impact:** the first missed Monday was 2025-08-18. The close reminders were not sent on that day or on any day afterward. Incident close reminders were not affected because they use their own inline check.
- **Fix:** `date.today().weekday() == calendar.MONDAY` in `src/dispatch/case/scheduled.py`. Regression tests in `tests/case/test_case_scheduled.py` failed on the old code and pass on the fix.

**Second issue:** the nightly `TypeError` comes from `case_close_reminder` subtracting `case.triage_at`, which is NULL for cases that reached Triage without running the triage transition flow. Known paths include the Slack reopen button, which sets the status directly, and case creation with a Triage status. The job now counts from `created_at` when `triage_at` is missing, and tests cover that. I have not changed those paths to set `triage_at`, and I could not tell from the logs which path produced the affected cases.

**Six-line summary for the report:**

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at