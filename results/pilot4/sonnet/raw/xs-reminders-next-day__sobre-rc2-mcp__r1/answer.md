Weekly case reminders are fixed: `_is_reminder_day()` now returns true on Mondays again. The new test fails on the old code and passes on the fix, and I haven't run the rest of the suite.

**Cause:** commit `c509d45e` ("share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The old inline check was `isoweekday() == 1`. The new one compared `isoweekday()` to `calendar.MONDAY`, which is 0. `isoweekday()` returns 1 for Monday, so the check was never true. `case_close_reminder` and `case_stable_reminder` both depend on it.

**Fix:** the check now uses `weekday() == calendar.MONDAY`, so both sides use the same numbering.

**Test:** `tests/case/test_case_scheduled.py` freezes the date across a full week plus the following Monday and asserts the check is true only on Mondays. With the fix reverted, the two Monday cases fail.

**Logs:** "Case close reminder sent" appears on Mondays 2025-07-28, 08-04 and 08-11, and never after the deploy on 08-13. The deploy was image `main-81d8ae42`, which contains `c509d45e`. The previous image, `main-b05613b5`, does not.

**Separate issue, not fixed:** `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime' and 'NoneType'` every day. It comes from cases in triage with no `triage_at`. It is caught per case, so it doesn't block other reminders, and it started before the regression.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18