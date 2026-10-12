**Root cause:** commit `c509d45e` broke the Monday check. It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which compares against `calendar.MONDAY`. In Python, `calendar.MONDAY` is 0 (weeks start at 0 on Monday), while `isoweekday()` returns 1 for Monday. The check is therefore never true, so the close and stable reminders never send. The refactor was meant to be a no-op and silently changed behavior.

- **Where:** `src/dispatch/case/scheduled.py`, `_is_reminder_day()`, used by `case_close_reminder` (triage) and `case_stable_reminder`.
- **Why triage daily reminders still arrive:** `case_triage_reminder` doesn't use the helper. It runs daily with no weekday check.

**The deploy:** `81d8ae42` ("fix(case): exclude resolved_by in update", #6183), built from `main` on 2025-08-12, contains `c509d45e`. It reached production on **2025-08-13 at 16:40 UTC**, when the scheduler and web containers started on `registry.example.com/dispatch:main-81d8ae42`. The previous scheduler image was `main-b05613b5`.

**Evidence from the logs:**
- Monday 2025-08-11 (old image): close and stable reminders went out to assignees.
- Monday 2025-08-18 (new image): no "Case close reminder sent" or "Case stable reminder sent" lines. The triage reminder still ran and sent.

**Fix (not applied, per your request):** either `date.today().isoweekday() == 1` or `date.today().weekday() == calendar.MONDAY`. `weekday()` is the variant that matches `calendar.MONDAY`.

The logs also show a separate nightly `ERROR` from `NoneType` in `triage_at` and `stable_at`, which is unrelated to this bug.

I saved these findings to the memory directory outside the repo. No code was changed.

----- next turn -----

Monday reminders were broken by a one-line weekday mismatch. It's fixed and covered by a regression test that fails on the old code.

**Cause:** Commit `c509d45e` refactored the Monday check into `_is_reminder_day()` as `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. The original inline code compared against `1`.

**Logs:** The scheduler logs show close and stable reminders sent on 07-28, 08-04, and 08-11, then nothing. The 18:00 case-reminder jobs kept running daily through 08-20, so the silence isn't a missing run. The deploy of `main-81d8ae42` on 2025-08-13 is the first with the bug.

**Changes (uncommitted in the working tree):**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): checks `_is_reminder_day()` for each day of a week by patching the module's `date`. Only Monday failed before the fix (`False is (0 == 0)`), and all 7 pass now.

`python -m pytest tests/case` passes (22 tests). I didn't run the full suite. The incident scheduler's `isoweekday() == 1` check is correct and I left it alone.

I also updated the memory note, which still said the fix wasn't applied.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18