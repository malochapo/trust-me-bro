**Recap**

- **Symptom:** the weekly Monday reminders for long-running triage and stable cases stopped after 2025-08-11. The daily triage reminders kept working.
- **Root cause:** commit `c509d45e` (2025-08-12) was a refactor that moved the Monday check into `_is_reminder_day()`. It compared `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. The check was never true, so both weekly jobs skipped every case without logging anything.
- **Deploy:** the scheduler and API pods moved to image `main-81d8ae42` at 2025-08-13T16:40Z. That image contains `c509d45e`, and the previous image `main-b05613b5` does not.
- **First missed Monday:** 2025-08-18. The last reminders went out on 2025-08-11, under the old code.
- **Evening TypeError:** `case_close_reminder` computed `utcnow() - case.triage_at`. Cases created directly in triage never run the transition flow that sets `triage_at`, so it was NULL. The error was caught and logged, and the job skipped those cases. This is separate from the outage but also cost those cases their reminders.
- **Fixes (uncommitted, tests in `tests/case/test_case_scheduled.py`):**
  - The weekday check now uses `weekday()`.
  - The close reminder counts from `triage_at or created_at`.
  - The new tests fail without the fixes and pass with them. I ran only that test file, not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at