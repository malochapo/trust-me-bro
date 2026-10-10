The weekly reminders stopped because of a Monday check that can never be true. I didn't line up the logs against the first missed Monday. Commit c509d45e (12 Aug 2025) matches the "since mid-August" timing and is the only change to this check, but I haven't confirmed it from the logs.

**Root cause.** The refactor moved the old inline check `date.today().isoweekday() == 1` into a shared helper, `_is_reminder_day()`. The helper compares against `calendar.MONDAY` instead. The two use different numbering:
- `isoweekday()` returns 1 for Monday through 7 for Sunday.
- `calendar.MONDAY` is 0.

So `isoweekday() == calendar.MONDAY` is never true on any day. `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both call the helper, so neither sends its weekly reminder. They fail silently, with no error logged. The daily triage reminder, `case_triage_reminder`, doesn't use the helper, which is why it still arrives.

**What the logs show.** The logs show nothing that points to a weekly send path being hit. There are no Monday close-reminder entries in `scheduler.log`. I did not trace what the "close reminder" matches in it are.

**Unrelated errors.** The logs also have a few `NoneType` subtraction errors at `triage_at`, plus a database connection-refused burst on 15 Aug. Neither explains a failure that lasts for weeks.

**Fix.** Use `date.today().weekday() == calendar.MONDAY`, or compare `isoweekday() == 1` as before.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so the check is never true and the weekly Monday close/stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f