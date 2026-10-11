The root cause is in `_is_reminder_day()`, which the refactor in `c509d45e` added. It compares `isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0 in Python, so the check is never true.

Commit `c509d45e` ("refactor(case): share the weekly reminder check") is dated Tue Aug 12 2025, which matches the mid-August start. Before it, both weekly paths compared against the literal `1`. The refactor swapped that for `calendar.MONDAY`, so `_is_reminder_day()` returns False every day.

Both weekly paths call it: `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases). The daily `case_triage_reminder` doesn't use it, which is why those still arrive. I confirmed `calendar.MONDAY == 0` and that Monday's `isoweekday()` is 1 in this environment. I did not check `api.log` for Monday send events, so the timing match comes from the commit date and the code.

The `scheduler.log` errors (`'datetime.datetime' and 'NoneType'` in `case_stable_reminder`) come from the earlier missing-`stable_at` bug, which `32fa810f` fixed. They are not the cause of this regression.

Fix: compare against `1` or `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`, which is the zero-based form that matches `calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The refactor compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the weekly Monday check never passes and both weekly reminders are suppressed.
INTRODUCED_BY: c509d45e