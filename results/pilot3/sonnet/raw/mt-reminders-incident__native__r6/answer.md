## Recap

**Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check is never true. Both `case_close_reminder` and `case_stable_reminder` call it, so they skipped every case on every day, with nothing in the logs.

**Deploy:** production moved from image `main-b05613b5` to `main-81d8ae42` on 2025-08-13 at about 16:40Z. `81d8ae42` is the first deployed commit that contains `c509d45e`.

**Timeline:**
- Monday 2025-08-11 (old build): case close reminders were sent.
- Monday 2025-08-18 (new build): none were sent. The stable reminder ran with no error and sent nothing. This was the first Monday after the deploy.

**Separate bug:** the evening `TypeError` came from `case_close_reminder` subtracting `case.triage_at`, which is None for cases that never went through the triage transition flow. That is the only place `triage_at` gets set.

**Fixes (uncommitted):**
- The weekday check now uses `weekday()`.
- The close reminder counts from `triage_at`, or from `created_at` when `triage_at` is missing.
- Regression tests are in `tests/case/test_case_scheduled.py`. They fail on the old code and pass now.

I left `case_stable_reminder` unchanged. It still skips cases with no `stable_at`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at