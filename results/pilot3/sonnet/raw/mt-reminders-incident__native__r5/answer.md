**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` (2025-08-12) refactored the inline Monday check into `_is_reminder_day()`. The helper compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1–7 and `calendar.MONDAY` is 0, so the check was never true. Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, silently skipped every day, with no error logged.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to the scheduler and web pods on 2025-08-13 at about 16:40 UTC. It replaced `main-b05613b5`. The log shows the last sends on Monday 2025-08-11 and none on Monday 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.
- **Second issue:** the evening TypeError came from triage cases with an empty `triage_at`. That column is nullable, with no backfill since 2022, and is only set when a case passes through the triage status flow. Those cases never got a weekly reminder. The job now counts from `created_at` when `triage_at` is missing.
- **Tests:** `tests/case/test_case_scheduled.py` covers the Monday and non-Monday cases for both jobs, plus the `created_at` fallback. `tests/case` passes (25 tests), and the new tests fail without the fixes.
- **Open items:** nothing is committed or deployed yet. `case_stable_reminder` still skips stable cases with no `stable_at`, which I left alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at