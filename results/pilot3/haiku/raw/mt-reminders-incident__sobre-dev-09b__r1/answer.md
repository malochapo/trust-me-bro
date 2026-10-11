The incident recap is below. The six lines at the end are the fields you asked for.

**Summary**

- **What broke:** Weekly close and stable reminders stopped going out after 2025-08-13. Daily triage reminders kept working.
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check could never pass.
- **Introduced:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced `isoweekday() == 1` with the helper that uses `calendar.MONDAY`.
- **Shipped:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler and web pods on 2025-08-13 at 16:40 UTC.
- **Impact:** Monday 2025-08-11 (before the deploy) sent 5 case close reminders. Monday 2025-08-18 sent none. The reminder settings were never changed.
- **Fix:** `date.today().weekday() == calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` fails on the old logic and passes on the fix.

**Secondary issue:** `case_close_reminder` logged a TypeError every evening from 2025-07-28 (later 2025-08-16 for the close job). It came from subtracting a NULL `triage_at` from the current time. `triage_at` is only set by the triage transition flow, and some paths put a case into triage without it, such as the Slack reopen handler. The fix counts from `created_at` when `triage_at` is missing, and the tests cover that case. The status-setting paths themselves are not yet fixed.

**Status:** Both fixes are uncommitted in the working tree. The tests I added and the existing `tests/case` suite pass (25 tests).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at