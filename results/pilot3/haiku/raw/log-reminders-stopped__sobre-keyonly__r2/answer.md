The root cause is in `_is_reminder_day()`, which the refactor commit `c509d45e` added. It compares `date.today().isoweekday()`, which returns 1 for Monday, against `calendar.MONDAY`, which is 0 in Python. The comparison is never true, so the weekly close and stable reminders never fire. The daily triage reminders don't use this check, so they keep arriving.

**Evidence**

- The last "Case close reminder sent" entries in `scheduler.log` are on 2025-08-11, a Monday. Commit `c509d45e` is dated 2025-08-12, and there are no close-reminder sends on 2025-08-18 (Monday) or after.
- Before the refactor the code was `date.today().isoweekday() == 1`. The refactor replaced the literal `1` with `calendar.MONDAY`. I confirmed `calendar.MONDAY == 0` and `isoweekday()` of a Monday is `1`.
- The triage reminder path (`case_triage_reminder`) has no weekday check, which is why it still works.

**Side note:** the deployed copy in the logs also throws `unsupported operand ... 'NoneType'` from `case_close_reminder` and `case_stable_reminder` every day. That is a separate issue (a missing `stable_at`/`triage_at` guard). The repo already has a `stable_at` guard from `32fa810f`, so the deployed build may be older than `main`. I did not change anything.

I did not change any code. The fix is to compare against `1` (or against `calendar.MONDAY` after calling `.weekday()` instead of `.isoweekday()`).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The refactor compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the weekly Monday check is never true and the close and stable reminders never send.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f