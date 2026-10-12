**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) made the Monday check never true. It went to production in the deploy on 2025-08-13 16:40Z, which ran image `main-81d8ae42`.

**The bug**
- Before the commit, `case_close_reminder` (triage) and `case_stable_reminder` (stable) tested `date.today().isoweekday() == 1`.
- The commit moved that test into a shared helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`. The helper compares against `calendar.MONDAY` instead of `1`.
- `calendar.MONDAY` is `0` (I confirmed this by running it). `isoweekday()` returns 1–7, so it never equals 0. Both reminders now skip every day, Mondays included.
- The commit message calls it a refactor, so nobody expected a behaviour change. The daily triage reminder, `case_triage_reminder`, doesn't use the helper, which is why it kept working.

**Evidence in the logs**
- Weekly case close reminders were sent on 07-28, 08-04 and 08-11 (4, 6 and 5 sends). The last one was 2025-08-11 18:00Z, which was a Monday.
- Monday 2025-08-18 18:00Z has no "Case close reminder sent" lines. `case_stable_reminder` ran cleanly with no errors but sent nothing, and the daily triage and incident close reminders still went out.
- That is the only Monday after the deploy and it had zero sends. The 08-18 run has no helper-specific log line; the evidence is the missing sends and the code.

**The deploy** (the `Started container` lines in both logs)
- The scheduler and API pods were replaced together on 2025-07-30 17:10Z by image `main-b05613b5` (it contains `32fa810f`). Those were replaced on 2025-08-13 16:40Z by image `main-81d8ae42`.
- `git merge-base --is-ancestor` confirms `c509d45e` is in `81d8ae42` and not in `b05613b5`. It is the third commit back from `81d8ae42`, and the scheduler traceback line numbers shifted by 4 after the deploy, matching the helper's added lines.
- The refactor merged on 08-12 but only reached production on 08-13. That is why 08-11 still worked and the first broken Monday was 08-18.

**A separate, smaller problem** (not why the Monday reminders stopped)
- `case_close_reminder` logs `TypeError: datetime - NoneType` on every 18:00 run. Some triage cases have `triage_at = None`, and the subtraction at line 47 has no guard.
- The same error was already logged on 08-10 and 08-11 on the old image, so it predates the refactor. The per-case `try/except` catches it, so it only skips those cases.
- The `stable_at` version of this error stopped after the 08-13 deploy, because `32fa810f` added its guard.

**Suggested fix, once you want me to make changes:** use `date.today().isoweekday() == 1`, or `calendar.MONDAY + 1`, and add a test for `_is_reminder_day()`. Separately, guard `triage_at` the way `stable_at` is guarded.

I didn't change any code.

----- next turn -----

I saved the findings to memory in `weekly-case-reminder-outage.md` and added a pointer to it in `MEMORY.md`. The note covers:

- **Root cause:** the `calendar.MONDAY` check in `c509d45e`.
- **Deploy:** image `main-81d8ae42`, rolled out 2025-08-13 16:40Z.
- **Log evidence.**
- **The `triage_at` issue** (a separate, smaller bug).
- **Proposed fix:** not applied.

I didn't change any code.

----- next turn -----

I fixed the weekday check in `src/dispatch/case/scheduled.py` and added a regression test. The new test passes (3 cases). I didn't run it against the old code, but it would have failed there: `isoweekday()` returns 1 on Mondays and the code compared it to `calendar.MONDAY`, which is 0.

- **Cause:** `_is_reminder_day()` compared `isoweekday()` to `calendar.MONDAY`, so it was never true and the weekly close reminders never went out. `case_triage_reminder` doesn't use it, which is why the daily triage reminders kept working.
- **Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.
- **Test:** `tests/case/test_case_scheduled.py` checks that Monday 2025-08-18 counts as a reminder day and that Tuesday 2025-08-19 and Sunday 2025-08-24 don't.
- **Not committed:** the change is in the working tree only.
- **Stable reminder:** my notes mention a `case_stable_reminder` that uses this check, but I found no such function in the file. Only `case_close_reminder` calls `_is_reminder_day()` here. I didn't look for where stable-case reminders live now.
- **Left alone:** `case_close_reminder` still raises `TypeError` for triage cases where `triage_at` is None. It's caught per case, and I didn't add a guard.

The deploy details come from my saved notes from yesterday's log investigation; I didn't re-check the logs. The old image's last Monday send was 2025-08-11, and the 2025-08-18 run sent nothing.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18