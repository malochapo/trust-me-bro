Monday reminders broke because `_is_reminder_day()` compares the wrong weekday numbering.

- **The bug:** `_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. The check is therefore never true on a Monday. It is true on Tuesday, but both reminders have already run on the previous Monday's schedule by then — no, they run daily at 18:00, so the check passes on Tuesday only in theory. In practice the logs show no sends after the change, which fits a check that has stopped matching Mondays.
- **Where it's used:** `case_close_reminder` (triage cases) and `case_stable_reminder` both gate on it.
- **Timeline:** Commit c509d45e (12 Aug 2025) replaced the original `isoweekday() == 1` with this helper.
  - "Case close reminder sent" appears in the scheduler log on 28 Jul, 4 Aug and 11 Aug, and never after.
  - The 13 Aug logs show the line numbers in `scheduled.py` shifting, so the new code was live from then.
  - On Monday 18 Aug at 18:00, the triage reminder and the incident close reminder fired, but no case close reminder was sent.
- **Why the daily triage reminders still work:** `case_triage_reminder` doesn't use this check.
- **Unrelated noise:** The `TypeError … NoneType` errors in the logs come from a case with no `triage_at` (or `stable_at` for the stable reminder). They were already there before the change and are caught per case. They aren't why the reminders stopped.

I haven't run the code to confirm what the check returns on a Tuesday. The diagnosis rests on the commit diff and on the absence of sends after 11 Aug.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the Monday check never matches and the weekly case reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f