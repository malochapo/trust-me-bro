The root cause is an off-by-one in the new weekly-reminder helper. It compares `isoweekday()`, where Monday is 1, against `calendar.MONDAY`, where Monday is 0.

**Evidence from the logs**
- On Mondays 07-28, 08-04 and 08-11 the scheduler sent "Case close reminder sent to …" messages.
- On Monday 08-18, after the 08-13 deploy, none were sent, and `case_stable_reminder` ran cleanly with no sends. The daily triage reminders kept going throughout.
- The only close reminders after 08-13 went out on Mondays, so the check now matches no day at all.
- The `NoneType` errors on `triage_at` and `stable_at` are a separate, older issue. They appear on every day through 08-12 while the Monday reminders were still being sent. They are caught per case, so they don't block the other cases.

**Code**
- Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`.
- It returns `date.today().isoweekday() == calendar.MONDAY`.
- The code it replaced was `date.today().isoweekday() == 1`.
- `calendar.MONDAY` is 0, while `isoweekday()` returns 1 for Monday and 7 for Sunday, so the comparison never matches.
- Both `case_close_reminder` (triage cases) and `case_stable_reminder` call the helper, so both stopped sending.
- The fix is `date.today().weekday() == calendar.MONDAY`, or going back to `isoweekday() == 1`.

I did not run the code or change any files.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so it never returns True and the weekly close/stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f