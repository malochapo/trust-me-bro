**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). It broke the Monday check in `src/dispatch/case/scheduled.py`.

**Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, which went live on 2025-08-13 at about 16:40Z. The scheduler pod `scheduler-mhtsgqwwx-q5q2n` and the web pod `web-5dkmr9s9s-xxktx` both started on that image. The deploy replaced `main-b05613b5`, which had been running since 2025-07-30 17:10Z. `81d8ae42` is the last commit in the 08-12 batch and includes `c509d45e`. `b05613b5` does not include it.

**The bug:**
- Before the commit, `case_close_reminder` and `case_stable_reminder` both checked `date.today().isoweekday() == 1`. `isoweekday()` returns 1 for Monday.
- The refactor moved that check into a helper, `_is_reminder_day()`, which compares against `calendar.MONDAY`.
- `calendar.MONDAY` is 0, because the `calendar` module counts days from Monday = 0. `isoweekday()` never returns 0, so the helper is always False.
- Both jobs now skip every case on every day, and no exception or log line is produced. The daily triage reminder is a separate job without this check, so it keeps working.

**Evidence in the logs:**
- Close reminders went out on Monday 07-28, 08-04 and 08-11, to the same six assignees each time. They stopped on Monday 08-18, after the deploy.
- On 08-18 the log shows an incident close reminder going out, and no case close reminders.

**Unrelated noise (the same on both sides of the deploy):** both jobs log `datetime - NoneType` errors from `case.triage_at` and `case.stable_at` being None for some cases. These errors appear from 07-28, well before the deploy. They hit only those individual cases, because each job catches exceptions per case, so they are not what stopped the reminders.

**Suggested fix, not applied as requested:** compare against `calendar.MONDAY` using `date.today().weekday()` instead of `isoweekday()`, or restore `isoweekday() == 1`. I'd also add a test that the helper returns True on a Monday.

----- next turn -----

I saved the findings to memory, so a new session can pick them up tomorrow.

The note covers:
- the root cause: `calendar.MONDAY` is 0 but `isoweekday()` returns 1 for Monday, so the new helper never matches;
- the commit that introduced it, `c509d45e`;
- the deploy image, `main-81d8ae42`, which went live on 2025-08-13 at about 16:40Z;
- the log evidence;
- the fix that is still pending.

No code has been changed.

----- next turn -----

The weekly close and stable reminders now go out on Mondays again. I haven't committed anything.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The check was never true, so `case_close_reminder` and `case_stable_reminder` skipped every case. Jordan Lee introduced it in `c509d45e` on 2025-08-12. It shipped in image `main-81d8ae42`, which went live on 2025-08-13 around 16:40Z. I rechecked the deploy time in the logs; the rest of the cause and the Monday evidence are from my notes from yesterday.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks the helper on all seven days of a week, true only on Monday. The new test passes with the fix. With the fix stashed, the Monday case fails (the other six days pass). I ran only this file, not the full suite.

I did not change the `datetime - NoneType` errors for cases with a missing `triage_at` or `stable_at`. They predate the deploy and are caught per case, so they didn't cause the outage.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18