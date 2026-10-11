The weekly Monday reminders stopped because of a refactor on 2025-08-12. The new helper compares ISO weekday numbers against `calendar.MONDAY`, and those two use different numbering.

- `_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`.
- `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I checked both in Python). The comparison is never true, so neither weekly reminder can fire.
- The old code compared against the literal `1`, which was correct. The refactor replaced it with `calendar.MONDAY` and broke it.

The logs agree:
- Monday 2025-08-11 (before the commit) still sent close reminders to r.patel, s.lindqvist, a.chen, m.okafor and k.tanaka.
- Monday 2025-08-18 (the first Monday after the commit) ran `case_stable_reminder` and `case_close_reminder` and sent nothing. The triage reminders still went out that day.

The `TypeError` on `case.triage_at` in `case_close_reminder` and the `stable_at` `NoneType` errors appear on most days. They are caught per case, so they are log noise and do not explain the missing Monday reminders. They are a separate issue worth its own fix.

The fix is to compare against the ISO value (`== 1`), or against `calendar.MONDAY + 1`, or better, to use `date.today().weekday() == calendar.MONDAY`, which is the value the `calendar` constant is meant for. I have not changed the code.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The helper compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the Monday check is never true and the weekly close and stable reminders never send.
INTRODUCED_BY: c509d45e