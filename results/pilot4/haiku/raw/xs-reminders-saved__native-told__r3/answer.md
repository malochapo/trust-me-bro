The weekly Monday reminders are fixed in the working tree, with a regression test. I did not commit.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The check was never true, so the weekly close and stable reminders stopped. The daily triage reminder has no weekday gate, so it was unaffected. The logs agree: the last Monday with sends was 2025-08-11 (5 close reminders and 1 stable), and 2025-08-18 sent none.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` also counts Monday as 0, so it matches the constant.

**Regression test:** `tests/case/test_case_scheduled.py` pins "today" across a full week and checks that only Monday returns true. It fails on the buggy code for Monday, and passes after the fix.

**Results:** the case tests pass (22). The full suite has 8 failures in `tests/ai/test_ai_service.py` and two service tests. All 8 also fail on the original code, so they are unrelated to this change.

I also updated the saved memory note to match this state.

Not changed: `case_close_reminder` still computes `datetime.utcnow() - case.triage_at` without a None check, which produces the daily `datetime - NoneType` errors in the logs. The stable reminder already guards against this. It's a separate issue, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18