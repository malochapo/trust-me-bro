**Root cause:** `calendar.MONDAY` is `0` in Python, but `isoweekday()` returns `1` for Monday. The helper compares the two, so it is never true, and both weekly reminders are silently skipped.

**The code:** `src/dispatch/case/scheduled.py:31-33`, added in `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check"):

```python
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

The refactor replaced `date.today().isoweekday() == 1`, which was correct. `_is_reminder_day()` is used by `case_close_reminder` (triage) and `case_stable_reminder`. I checked the values: `calendar.MONDAY == 0`, and `date(2025, 8, 18).isoweekday() == 1`. The daily `case_triage_reminder` does not call the helper, which is why it still fires.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at `2025-08-13T16:40:06Z` (`scheduler.log`). `81d8ae42` ("fix(case): exclude resolved_by in update", #6183) is a descendant of `c509d45e`, so the broken helper is in that release. The web pod got the same image at 16:40:07 (`api.log`). I inferred the commit from the tag name and did not check the registry.

**Log evidence:**
- Monday 2025-08-11 (before deploy): close reminders sent to r.patel, s.lindqvist, a.chen, m.okafor, k.tanaka.
- Monday 2025-08-18 (after deploy): the job runs (`case_stable_reminder` elapsed line at 18:00), but no "Case close reminder sent" lines appear.
- The daily triage reminders continue on 08-13 through 08-20.

**Separate issue, already fixed in the same release:** `case_stable_reminder` logged a `NoneType` subtraction error on every run from 07-28 until 08-12, because some stable cases have no `stable_at`. Commit `32fa810f` ("fix(scheduler): not all cases have a stable_at date") added the guard, and that error stops after the 08-13 deploy. It was logged per case and caught, so it was noise rather than the cause of the missing reminders.

**Suggested fix, not applied:** either revert the helper to `date.today().isoweekday() == 1`, or write it as `date.today().weekday() == calendar.MONDAY`, since `weekday()` is 0-based like `calendar.MONDAY`. Whichever you choose, add a test that pins a Monday date. No code has been changed.

----- next turn -----

I saved the findings to a memory file so a new session can pick them up.

- **File:** `memory/case-weekly-reminders-missing-root-cause.md`, with an index line in `memory/MEMORY.md`.
- **What it records:** the root cause (`_is_reminder_day()` compares `isoweekday()` to `calendar.MONDAY`, which is `0`), the commit that introduced it (`c509d45e`), the deploy that shipped it (`main-81d8ae42`, started 2025-08-13 16:40 UTC), and the log evidence (close reminders sent on Monday 08-11, none on Monday 08-18).
- **What's still open:** which fix to apply, either reverting to `== 1` or using `weekday() == calendar.MONDAY`, plus a Monday-pinned test. No code has been changed.
- **Caveat:** the deploy-to-commit mapping is inferred from the image tag and I did not check the registry.

Tomorrow, the first step is to confirm the helper is still unchanged on main, then ask which fix option you want.

----- next turn -----

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