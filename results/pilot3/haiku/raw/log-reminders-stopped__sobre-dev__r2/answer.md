The root cause is a day-of-week constant mismatch in `_is_reminder_day()`, introduced by commit `c509d45e` on Aug 12.

`_is_reminder_day()` compares `date.today().isoweekday()` to `calendar.MONDAY`. But `calendar.MONDAY` is `0` (Python counts Monday as 0), while `isoweekday()` returns `1` for Monday. The comparison is therefore never true, so the weekly gate never opens. The commit replaced the old `date.today().isoweekday() == 1` checks with this helper, which quietly broke them.

The logs confirm the timing. On Monday 2025-08-11, the scheduler sent several "Case close reminder sent" messages. On Monday 2025-08-18, no case close or stable reminders were sent, only incident close reminders. The daily triage reminders (`case_triage_reminder`) don't use this helper, which is why they still arrive.

The same helper also gates `case_close_reminder` (triage cases), so those weekly reminders are affected too, not just the stable ones. The `NoneType` tracebacks from `case_stable_reminder` in the logs are a separate issue. The repo version already guards `stable_at` (commit `32fa810f`), so the deployed code appears to be older than HEAD. That doesn't explain the mid-August change.

The fix is to compare against `1` (or use `date.today().weekday() == calendar.MONDAY`). I haven't made or tested the change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the weekly Monday gate is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f