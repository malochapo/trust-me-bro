The root cause is a weekday constant mismatch in `_is_reminder_day()`, introduced by commit `c509d45e`.

`_is_reminder_day()` compares `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0 in Python. The comparison is never true, so `q >= 1 and _is_reminder_day()` is always false, and the weekly close reminders for triage and stable cases are never sent. The daily triage reminders come from `case_triage_reminder`, which has no weekday check, so they keep working.

Evidence:
- The last weekly close reminders were sent on Monday 2025-08-11 (`Case close reminder sent to m.okafor@...` and `k.tanaka@...` in `scheduler.log`). None appear on 2025-08-18.
- `c509d45e` (Aug 12) replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which uses `calendar.MONDAY`. In this environment `calendar.MONDAY == 0` and `datetime.date(2025,8,11).isoweekday() == 1`.

The original literal `1` was correct. The commit's message says it is a refactor, but it changed behavior.

A separate issue, not the cause: `case_close_reminder` subtracts `case.triage_at` without a None check, so `TypeError` shows up in the logs for cases that have no `triage_at`. The per-case `try/except` contains it, but it is a real bug and the same `None` problem was fixed for `case_stable_reminder` in `32fa810f`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the Monday check is never true and the weekly reminders never fire.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f