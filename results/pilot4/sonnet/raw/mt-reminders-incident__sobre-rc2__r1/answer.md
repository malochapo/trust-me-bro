## Recap

**Symptom:** since mid-August, assignees stopped getting the weekly Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Weekday bug**
- Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the inline Monday check into a helper, `_is_reminder_day()`.
- The helper compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true.
- Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, skipped every case on every day. Nothing was logged, because skipping looks the same as having nothing to send.
- The daily triage reminder doesn't use the helper, so it kept working.
- The scheduler pod started on image `main-81d8ae42` on 2025-08-13 at 16:40 UTC, and the web pod started on the same image seconds later. That image includes the refactor.
- Monday 08-11 ran on the old image (`main-b05613b5`) and sent reminders. Monday 08-18 ran on the new image and sent none.
- The fix is to use `weekday()`, which counts Monday as 0 and matches `calendar.MONDAY`.

**Evening TypeError**
- `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set when a case moves into triage through `case_triage_status_flow`, so other triage cases have none.
- The error was caught and logged per case on every 18:00 run, and those cases never got a weekly reminder.
- The fix counts from `created_at` when `triage_at` is missing.
- The stable-case job still skips cases without `stable_at`.

**Code changes**
- Both fixes are in `src/dispatch/case/scheduled.py`.
- The tests are in `tests/case/test_case_scheduled.py`.
- I ran only that test file, not the full suite, and nothing is committed or deployed. Production keeps missing the Monday reminders until a build with these changes ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at