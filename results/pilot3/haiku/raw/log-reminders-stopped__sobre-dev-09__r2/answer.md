The root cause is in `_is_reminder_day`, which compares Python's `date.isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check is never true, so no Monday reminders go out.

- **The change:** commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`. The new helper uses `calendar.MONDAY`, which is 0 in Python's `calendar` module (Monday is 0 there, not 1).
- **Verified:** `calendar.MONDAY` is 0, and `date(2025, 8, 11).isoweekday()` is 1.
- **Logs:** "Case close reminder sent" lines appear on 2025-07-28 (4), 2025-08-04 (6) and 2025-08-11 (5). The 2025-08-11 batch predates the commit. No close reminders appear on 2025-08-18, the first Monday after the commit, and the logs run through 08-20.
- **Why only long-running cases:** the triage and stable reminders are gated on this same weekly check. Both `case_close_reminder` and `case_stable_reminder` call it, so both go silent. The daily triage reminder in `case_triage_reminder` does not use it, which is why those still arrive.
- **Red herring:** the scheduler logs also show daily `unsupported operand type(s) ... 'NoneType'` errors from `case_close_reminder` and `case_stable_reminder`. These come from `triage_at` or `stable_at` being `None` and are caught per case. They don't explain the Monday silence, since the stable-reminder code path in the repo already guards against `None`.

The fix is to compare against `1`, or to use `date.today().weekday() == calendar.MONDAY`, which is 0-based on both sides. I haven't changed the code or added a test.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The helper compares date.isoweekday() (Monday=1) with calendar.MONDAY (Monday=0), so the weekly Monday check is never true and the long-running close reminders stop.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f