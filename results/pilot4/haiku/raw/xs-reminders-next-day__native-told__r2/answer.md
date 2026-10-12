The Monday weekly reminders were never sent after the 2025-08-13 deploy because of a weekday off-by-one, and that is now fixed.

**The bug:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It was never true, so `case_close_reminder` and `case_stable_reminder` skipped every Monday. Commit `c509d45e` introduced it when it replaced the inline `isoweekday() == 1` check with the helper.

**The logs confirm it:** Close reminders were sent on 2025-07-28, 2025-08-04, and 2025-08-11 (old image `main-b05613b5`, which predates `c509d45e`). The scheduler switched to `main-81d8ae42` at 2025-08-13 16:40 UTC, and no close or stable reminders were sent on 2025-08-18 or later (the log runs to 2025-08-20). Daily triage and incident reminders kept running, since they don't use this check.

**The fix:** I changed the check to `date.today().weekday() == calendar.MONDAY`. The incident scheduler's `isoweekday() == 1` check is already correct and I left it alone.

**The regression test:** `tests/case/test_case_scheduled.py` patches `date` in the scheduler module and checks `_is_reminder_day()` for each day of one week. Before the fix it failed on Monday; after the fix all seven days pass. `python -m pytest tests/case` passes (22 tests).

**Full suite:** 366 passed, 8 failed, 4 skipped. The same 8 tests fail with the fix stashed, so they are unrelated: four in `tests/ai/test_ai_service.py`, `test_restricted_case_filter_with_test_data`, and `test_find_entities_with_field_only`.

**Not changed:** `case_close_reminder` still raises a `TypeError` for cases with `triage_at` None. It's caught per case, so it doesn't block the other reminders, but it logs an error every day. The stable path was guarded in `32fa810f`, and the same guard would fix this. I didn't change it because it's outside this bug.

The changes are uncommitted in the working tree. I also updated the saved memory note with the fix status.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18