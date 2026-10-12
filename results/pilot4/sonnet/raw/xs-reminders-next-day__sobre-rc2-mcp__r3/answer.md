Assignees have not received the weekly close reminders since the Monday after a refactor shipped. I fixed the check, and the new tests pass with the fix and fail on the old code.

**Cause:** commit `c509d45e` ("share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`. The new helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The condition is never true, so both the close and the stable reminders silently stopped. No errors are logged.

**Evidence from the logs:**
- The scheduler log shows "Case close reminder sent" on 2025-07-28, 08-04 and 08-11, and never again.
- The commit was made on 2025-08-12 and went out in image `main-81d8ae42`, started on 2025-08-13T16:40. The previous image was `main-b05613b5`.
- The first Monday after that deploy is 2025-08-18.

**Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, which compares like with like. I left `calendar` imported and added a comment on the off-by-one.

**Tests:** I added `tests/case/test_case_scheduled.py`. It checks `_is_reminder_day()` for 14 consecutive days. It also checks that `case_close_reminder` sends only on a Monday, for a case triaging 10 days. All 16 pass with the fix. Against the old code, 3 of them fail. I did not run the rest of the suite.

I did not write a separate test for `case_stable_reminder`. It shares the same helper, so the helper test covers it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18