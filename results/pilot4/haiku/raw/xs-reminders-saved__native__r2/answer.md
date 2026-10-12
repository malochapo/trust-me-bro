Fixed. The weekly Monday reminders were never sent because `_is_reminder_day()` compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so it was always False. I changed it to `date.today().weekday() == calendar.MONDAY` in `src/dispatch/case/scheduled.py`.

The regression test is `tests/case/test_case_scheduled.py`. It freezes `date` and checks every weekday, and the Monday case fails on the old code. All 23 tests in `tests/case` pass. The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail on the untouched code, so they predate this change.

The logs show the regression in `main-81d8ae42`, deployed 2025-08-13. Monday 2025-08-11 at 18:00 sent close and stable reminders on the previous build. Monday 2025-08-18 at 18:00 sent none. The memory note I had from yesterday was accurate, and I updated it.

Choices I made:
- I used `weekday()` rather than the `== 1` option my notes suggested, since it matches `calendar.MONDAY` directly.
- I did not commit. The change and the new test file are uncommitted in the working tree.
- I did not fix the separate `case_close_reminder` crash on cases with no `triage_at`. It is caught per case, so it does not stop other reminders, but those cases still get none. It needs its own guard and is a good follow-up.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18