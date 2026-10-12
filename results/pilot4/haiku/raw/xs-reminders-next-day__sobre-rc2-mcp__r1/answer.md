The weekly reminders were dropped because the Monday check compared the wrong numbering. I've fixed it and added a regression test.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` skipped every day. The bug came in with `c509d45e` on 2025-08-12, which refactored the check into this helper. The scheduler logs show reminders on Mondays 2025-08-04 and 2025-08-11, then none after that. The first missed Monday was 2025-08-18, and the logs run through 2025-08-20 with no close reminders sent that day. The scheduler started the image `main-81d8ae42` on 2025-08-13, and that image contains `c509d45e`.

**Changes:**
- `src/dispatch/case/scheduled.py`: `isoweekday()` is now `weekday()`, which uses the same 0-based numbering as `calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): checks that only Monday returns true across a full week, and that Monday 2025-08-18 is a reminder day. Against the old code, the Monday cases fail, and with the fix all 8 pass. `python -m pytest tests/case` passes (23 tests).

The change is not committed.

**Not fixed, but noticed:** the scheduler log has `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors on `case.triage_at` in `case_close_reminder`, every day from 2025-07-28 onward. The per-case `try` catches them, so those cases are skipped silently. This predates the weekday bug and needs a separate fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18