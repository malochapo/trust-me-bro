Weekly reminders were not sent from Monday 2025-08-18 because the Monday check could never be true. The fix is one line, and a regression test covers it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()`, which returns 1 for Monday, with `calendar.MONDAY`, which is 0. The check was never true, so the close reminders for triage and stable cases were skipped every day. Commit `c509d45e` introduced it by moving the check into that helper. It shipped in image `main-81d8ae42`, and the scheduler started on that image on 2025-08-13 at 16:40. The logs confirm it: Monday 2025-08-11 sent 5 case close reminders, and Monday 2025-08-18 sent none. Incident reminders still fired on 2025-08-18 because `incident/scheduled.py` uses its own correct check.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` becomes `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): patches `date` in the scheduled module and walks a full week starting Monday 2025-08-18. It asserts the helper is true only on Monday. It failed on the old code and passes now.

**Verification:** `python -m pytest tests/case` passes (16 tests). I did not run the full suite. Nothing is committed.

**Open item, not changed:** the logs also show `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors from `case_close_reminder`, around `scheduled.py:47`, where `case.triage_at` is used without a `None` check. `case_stable_reminder` has that guard now, but `case_close_reminder` doesn't. I did not look at whether these errors continued after the deploy.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18