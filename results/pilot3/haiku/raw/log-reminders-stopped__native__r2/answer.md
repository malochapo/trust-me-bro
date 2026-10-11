The root cause is the weekday check in `_is_reminder_day()`, introduced by the refactor in commit `c509d45e`. It compares `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so it is never true and the Monday-only reminders never fire.

**What changed:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) replaced the inline `date.today().isoweekday() == 1` with a new helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

**Why it breaks:** `calendar.MONDAY` is `0` in Python (the week starts on Monday = 0), while `isoweekday()` returns `1` for Monday. I confirmed both values with the local Python. So `_is_reminder_day()` returns `False` every day of the week.

**Why only the weekly reminders are affected:** `case_close_reminder` (triage) and `case_stable_reminder` (stable) both gate their sends on `q >= 1 and _is_reminder_day()`. The daily triage reminder in `case_triage_reminder` does not use this helper, so it keeps sending. That matches the symptom.

**Timing in the logs:** The refactor landed on 2025-08-12, and the first Monday after it is 2025-08-18. On that date, `scheduler.log` shows the close-reminder job running, but no case close or stable reminder is sent.

**Side note, not the cause:** The scheduler log also shows `TypeError: ... 'datetime.datetime' and 'NoneType'` from both the stable and triage jobs on the Monday, which is `case.stable_at` / `case.triage_at` being `None`. Commit `32fa810f` guarded the stable path with `if case.stable_at:`, but the triage path has no such guard. That is a separate bug, but it would also block triage reminders for cases without `triage_at`.

**Fix:** Compare against `date.today().isoweekday() == 1`, or against `calendar.MONDAY + 1`. Better still, have the helper check `date.today().weekday() == calendar.MONDAY`, which uses the same 0-based convention as `calendar.MONDAY`. The `_is_reminder_day` helper is only called from `scheduled.py` in this repo; I did not check whether any test relies on the old behaviour.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The helper compares `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so the Monday check is never true and the weekly stable and triage reminders never send.
INTRODUCED_BY: c509d45e