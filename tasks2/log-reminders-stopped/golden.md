The weekly close and stable reminders are gated by _is_reminder_day, which compares isoweekday() (Monday = 1) with calendar.MONDAY (0), so it is never true.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: isoweekday() returns 1 on Mondays but calendar.MONDAY is 0, so the Monday check never passes.
INTRODUCED_BY: {plant:q4-reminder-day}
