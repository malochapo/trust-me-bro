Monday reminders are fixed. The new tests pass with the fix and fail without it (3 of 6 fail on the old code). I ran only the new test file, not the full suite.

**Cause:** `_is_reminder_day()` compared `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0), so it was never true on any day. That silently stopped `case_close_reminder` and `case_stable_reminder`. Both ran at 18:00 daily and raised no error. `case_triage_reminder` doesn't use the helper, so it kept working.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`, in `src/dispatch/case/scheduled.py`.

**Test:** `tests/case/test_case_scheduled.py` does two things:
- It checks the helper is true only on a Monday.
- It runs both weekly jobs with a 15-day-old case and checks the reminder is sent on Monday 2025-08-18 and not on Tuesday 2025-08-19.

I checked the dates in the logs. The last sends were on Monday 2025-08-11. The `main-81d8ae42` image started on 2025-08-13, a Wednesday, so 2025-08-18 was the first Monday without reminders.

The null `triage_at` error in the logs is a separate issue, and I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18