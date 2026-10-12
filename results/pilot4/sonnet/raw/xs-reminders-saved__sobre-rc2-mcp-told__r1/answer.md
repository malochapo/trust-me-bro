Weekly reminders were never sent after the 2025-08-13 deploy because the Monday check could never be true. I fixed it and added a regression test.

**Cause:** commit c509d45e ("share the weekly reminder check") moved the inline `date.today().isoweekday() == 1` into a shared helper. The helper compares `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0). So `_is_reminder_day()` always returned False on Mondays, and both `case_close_reminder` (triage) and `case_stable_reminder` skipped every week.

**Evidence from the logs:**
- Close reminders were sent on 07-28, 08-04 and 08-11.
- On 08-18 only the triage reminder went out.
- The 08-13 deploy, image `main-81d8ae42`, contains c509d45e.

**Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now uses `weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` has 13 cases. They check that the helper is true only on Monday, and that both tasks send a reminder on Monday and none on other days. The tests pass with the fix. With the fix stashed, the three Monday cases fail.

**Unrelated errors in the logs:** the scheduler also logs a caught `datetime - None` error every day from `case_close_reminder` and `case_stable_reminder`. I didn't touch it; it comes from some cases having no `triage_at`, and the code at the log's line numbers (47 and 93) matches the current file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18