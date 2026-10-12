Recap of the reminder incident and the two fixes:

- **Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept going out.
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so both weekly reminder jobs sent nothing.
- **How it shipped:** `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) introduced the check. It reached production in `main-81d8ae42`, which started on the web and scheduler containers at 2025-08-13 16:40 UTC. The last Monday with sends was 2025-08-11, before the deploy. The first missed Monday was 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. The regression tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix.
- **Evening TypeError:** The close reminder subtracted `case.triage_at` from `utcnow()`. Cases that reached triage without that timestamp raised a TypeError, which the per-case `try` caught and logged. The paths that skip `triage_at` are: transitions into Triage from Escalated or Stable, cases created directly in Triage, and status edits through `service.update()`. I couldn't confirm which one produced the production rows, because the logs don't record case IDs. The job now counts from `created_at` when `triage_at` is missing, and a test covers that.
- **Still open:** The stable reminder still skips cases without `stable_at` and does not fall back to a timestamp. The 8 failures in `tests/ai`, `tests/database`, and `tests/entity` predate these changes and are unrelated.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at