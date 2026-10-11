The root cause is in `_is_reminder_day` in `src/dispatch/case/scheduled.py`. It compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, which is the numbering `weekday()` uses. The comparison is therefore never true on a Monday. It is true on no day of the week, because `isoweekday()` only returns 1 to 7. Both weekly reminders pass through this check: `case_close_reminder` for triage cases and `case_stable_reminder` for stable cases. Neither sends anything now. The daily triage reminder doesn't use the check, which fits what you see.

Commit c509d45e (2025-08-12, "refactor(case): share the weekly reminder check") introduced it. It replaced the inline `date.today().isoweekday() == 1` in both functions with this helper. The timing matches the start of the problem in mid-August.

I did not find any log line showing a weekly reminder being sent or skipped. The logs can't show it directly, because the weekly path writes nothing when the check fails. I got there by reading the code and checking the constants.

The scheduler log also has a daily "unsupported operand ... NoneType" error. It comes from cases with a missing `triage_at` or `stable_at`, and it appears every day from 2025-07-28 to 2025-08-20. The code catches and logs it per case, so it doesn't stop other cases from being processed. It is a separate, older issue and not the cause of the missing reminders.

The fix is to compare against 0 with `date.today().weekday()`, or to compare `isoweekday()` with 1.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so the check never matches and the weekly triage and stable close reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f