The weekly Monday reminders were never sent because a weekday check compared against the wrong number. The fix is in and a regression test covers it. Nothing is committed.

**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). Monday never matched, so `case_close_reminder` and `case_stable_reminder` skipped every Monday. Commit `c509d45e` (a refactor that moved the check into this helper) introduced it. The original code used `isoweekday() == 1`, which was correct.

**Evidence from the logs:**
- The last close/stable reminders were sent on Monday 2025-08-11, before the refactor's deploy.
- The first deploy containing `c509d45e` was `main-81d8ae42`, which started on 2025-08-13.
- On Monday 2025-08-18 there are no case close or stable reminder entries. The incident close reminder, which uses the correct `isoweekday() == 1`, still ran that day.

**Changes:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`, so the two agree.
- `tests/case/test_case_scheduled.py` (new): a parametrized test patches `date` in the module and checks that `_is_reminder_day()` is true on Monday and false on Tuesday through Sunday. Against the original code it fails on Monday, and it passes with the fix.

**Verification:** `python -m pytest tests/case` passes (22 tests, including the 7 new cases). I did not run the full suite.

**Not addressed:** the scheduler logs an error every day for `case_close_reminder`, because `case.triage_at` is `None` for some cases. The per-case try/except keeps this from blocking other cases, but it is noisy and worth a follow-up.

I did not have yesterday's findings in this conversation. I rebuilt the diagnosis from the logs and the repo.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18