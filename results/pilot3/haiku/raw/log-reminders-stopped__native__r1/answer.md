The weekly stable and close reminders stopped because a refactor compared ISO weekday numbers against Python's `calendar.MONDAY`, which is 0, not 1.

**Root cause:** `_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this with `python3`). So the check is never true, and the weekly reminders never fire on any day. The daily triage reminder (`case_triage_reminder`) doesn't use this check, which is why it still arrives.

**Timeline:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Aug 12 2025) replaced the inline `date.today().isoweekday() == 1` with the helper. Before that commit the code compared against 1, so the Monday check worked. The first Monday after the change was Aug 18, which matches the report of reminders stopping in mid-August. The scheduler log does not show the stable reminder failing after Aug 12, which fits the check silently returning false from then on.

**Fix:** compare against `1` (or `calendar.MONDAY + 1`). The clearer option is to use `isoweekday() == 1` directly, since the helper's own docstring is about Mondays.

Note: the log errors (`case_stable_reminder` and `case_close_reminder` raising on a `None` timestamp) are a separate, earlier issue. The `if case.stable_at:` guard from `32fa810f` covers the stable case in the current code, and the `case_close_reminder` `None` errors don't explain the silent Monday skip.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The helper compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the Monday check is never true and the weekly stable and close reminders never send.
INTRODUCED_BY: c509d45e