**Root cause:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12) broke the Monday check.

- **The change:** it replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY`.
- **Why that never matches:** `calendar.MONDAY` is `0`, and `isoweekday()` returns 1–7 with Monday as 1. The comparison is never true.
- **Where it applies:** `case_close_reminder` (triage cases) and `case_stable_reminder`, both in `src/dispatch/case/scheduled.py`. Both go through `_is_reminder_day()`.
- **Why daily triage reminders still work:** `case_triage_reminder` has no weekday check.

**Evidence in the logs:**
- "Case close reminder sent" appears on 2025-07-28 (4), 08-04 (6) and 08-11 (5), the last at 18:00 UTC. It appears on no later date, and there is none on the Monday 08-18 run.
- 08-18 is the first Monday after the deploy that shipped the refactor.
- On 08-18 the 18:00 run of both jobs completed without sending anything.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`.
- The web pod `web-5dkmr9s9s` started it on 2025-08-13 at 16:40 UTC. The scheduler pod changed to `scheduler-mhtsgqwwx` on the same day.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", committed 08-12 at 14:47 -0700, and it contains `c509d45e`. The refactor itself shipped as a rider on this deploy.
- The previous deploy, `main-b05613b5` on 07-30, predates the refactor and sent reminders correctly on 08-04 and 08-11.
- I confirmed the deploy → commit mapping with `git merge-base --is-ancestor`, using the image tags in the api log. I didn't see the scheduler's image tag directly.

**Separate bug (not the cause):** the 18:00 runs on 07-28 and 07-29 log a `TypeError: datetime - NoneType`.
- Those traces point at `case.stable_at` and `case.triage_at`. The `stable_at` guard from `32fa810f` isn't in the 07-30 image; it ships in the 08-13 image.
- Since 08-13, only the `triage_at` error remains, once per run. It comes from a triage case with a null `triage_at`. The per-case `try/except` swallows it, so other cases are still processed.
- The 08-18 trace shows the exception at line 47 and the log line at 55, so the deployed file does match the refactored source.

**Fix when you want it:** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. A test for `_is_reminder_day()` on a Monday would have caught this. No code changed.

----- next turn -----

The weekly reminders for long-running triage and stable cases should send again on Mondays. The new test passes with the fix and fails without it. I ran only `tests/case/test_case_scheduled.py`, not the full suite.

**Cause:** commit `c509d45e` (Aug 12) moved the Monday check into a shared helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday but `calendar.MONDAY` is 0, so the check never passed. Both `case_close_reminder` (triage cases) and `case_stable_reminder` use the helper, so neither sent a reminder after the refactor.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.

**Regression test:** the new file `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` for a Monday, a Tuesday and a Sunday. It also runs both scheduled reminder functions on a Monday and a Tuesday with a case older than a week, and asserts the reminder is sent only on the Monday.

**Timeline from the logs:**
- Aug 11 was the last Monday the close reminders were sent.
- The scheduler and API both moved to image `main-81d8ae42` on Aug 13, 16:40 UTC. That image contains `c509d45e`.
- On Aug 18 at 18:00 the close and stable reminder jobs ran and sent nothing.

**Separate bug, not fixed:** the scheduler log shows `case_close_reminder` failing every day with `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` (`case.triage_at` is `None`). That predates this bug, since it appears in the July logs too, and the per-case `try` already catches it. It is probably still skipping those cases' reminders, so it needs its own look.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18