The Monday reminders are fixed in the working tree. The bug was a weekday comparison that could never be true, so the close and stable reminders never went out on Mondays. Nothing is committed yet.

**The fix:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). It now uses `date.today().weekday() == calendar.MONDAY`, which is 0-based like the constant. I chose this over reverting to the literal `1` because it keeps the named constant.

**The regression test:** `tests/case/test_case_scheduled.py` runs the check across a full week starting Monday 2025-08-18. On the old code it fails for Monday only. On the fix all seven days pass. The full `tests/case` suite passes (22 tests) under `python -m pytest`. I could not run ruff because it isn't installed here.

**Evidence from the logs:**
- Close-reminder sends happened on Mondays 2025-07-28, 08-04 and 08-11.
- None on 2025-08-18. The job ran every day, but no Monday sends appear.
- Triage reminders kept going daily because they don't use this helper.
- Image `main-81d8ae42` (`fix(case): exclude resolved_by in update`, #6183) is the first deploy containing `c509d45e`. It started on the scheduler at 2025-08-13T16:40:06Z. I checked that the tag maps to that commit in the repo.

I also updated the saved memory note, which still said the fix was pending.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18