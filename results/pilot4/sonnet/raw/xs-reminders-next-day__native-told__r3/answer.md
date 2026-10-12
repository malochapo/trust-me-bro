Fixed and tested: the new tests pass with the fix and fail (3 failures) without it.

**Cause:** commit c509d45e ("share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compares `date.today().isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0). That is never true, so `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending anything. Before the refactor the code was `isoweekday() == 1`.

**Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` checks the day check for all 7 weekdays. It also runs both reminder tasks on a Monday, Tuesday and Sunday and asserts the reminder is sent only on Monday.

**Evidence from the logs:**
- The commit's changes first ran in the 2025-08-13 deploy, image `main-81d8ae42`. The earlier image, `main-b05613b5`, does not contain it.
- Monday 2025-08-11 had 5 "Case close reminder sent" lines, from the old image.
- Monday 2025-08-18 had none, only the triage reminder and the incident reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18