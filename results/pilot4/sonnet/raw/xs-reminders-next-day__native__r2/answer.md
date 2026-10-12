Weekly reminders will go out on Mondays again. The new tests pass with the fix and fail on the old code (3 failures, including both Monday cases).

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. That silenced both the triage close reminder and the stable close reminder. I changed it to `date.today().weekday()`, which does use 0 for Monday.

**Regression test:** `tests/case/test_case_scheduled.py` checks that the helper is true only on Monday. It also checks that `case-close-reminder` and `case-stable-reminder` send on Monday and not on other days.

**Timeline from the logs:**
- Close reminders went out on Mondays 07-28, 08-04 and 08-11.
- Commit c509d45e, which introduced the bug, is dated 08-12.
- Image `main-81d8ae42` was deployed on 08-13, and it contains that commit.
- The first Monday after that was 08-18, and no case close reminders went out that day. Only an incident close reminder and the daily triage reminder did.

**A separate problem I did not fix:** the scheduler log shows a daily `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` error in `case_close_reminder`. A case in triage has no `triage_at` value. That is a data or logic issue that would hide reminders for that case even with this fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18