**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check.

It replaced the inline `date.today().isoweekday() == 1` with a helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (I checked: it prints 0). So the condition is never true on any day.

This one check gates `case_close_reminder` (triage cases older than a week) and `case_stable_reminder` (stable cases older than a week). Both stopped sending, and nothing logs an error. The daily triage reminder has no day check, so it is unaffected. No reminder settings changed.

**Deploy that shipped it:** the production rollout on 2025-08-13 at about 16:40Z.
- The scheduler pod went from image `dispatch:main-b05613b5` to `dispatch:main-81d8ae42`, and the web pod changed to the same image.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", from 2025-08-12.
- `c509d45e` is an ancestor of it, so the image includes the refactor.
- The previous image, `b05613b5`, dates from 2025-07-29 and predates the refactor.

**Evidence from the logs:**

| Monday | "Case close reminder sent" lines | Image running |
|---|---|---|
| 2025-07-28 | yes (4 lines in the first output, which I cut at 12 lines, so there may be more) | `b05613b5` |
| 2025-08-04 | 6 | `b05613b5` |
| 2025-08-11 | 5 | `b05613b5` |
| 2025-08-18 | 0 | `81d8ae42` |

2025-08-18 was the first Monday on the new image, and it is the only Monday with no sends. That matches "since mid-August".

**Unrelated noise in the logs:**
- The `TypeError: datetime - NoneType` tracebacks appear daily from 07-28 to 08-20. They come from cases with no `triage_at` or `stable_at`. `32fa810f` guarded only `stable_at`, and the `case_close_reminder` error at `scheduled.py:51` still fires through 08-20. These are caught per case and don't cause the missing Monday reminders.
- The database "starting up" errors on 08-15 are also unrelated.

I haven't changed any code. The fix would be to compare against `calendar.MONDAY + 1`, or more simply `date.today().weekday() == calendar.MONDAY`. A small test for the helper would stop this recurring. Say if you want me to make that change.

----- next turn -----

I saved the findings to memory in `monday-reminder-regression.md` and added a line to `MEMORY.md`. The note covers:
- the root cause (commit `c509d45e`),
- the deploy that shipped it (image `main-81d8ae42`, rolled out 2025-08-13 at about 16:40Z),
- the log evidence and the unrelated noise,
- the proposed fix.

It also says no code has been changed and that we're waiting for your go-ahead. A new session can pick up from there.

----- next turn -----

I fixed the bug. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, which is 0. The check could never be true, so `case_close_reminder` and `case_stable_reminder` never sent anything. It now uses `weekday()`, where Monday is 0.

I added `tests/case/test_case_scheduled.py`. It checks a Monday, a Sunday, a Tuesday and a Wednesday. The four cases pass with the fix. With the old code, the Monday case fails, so the test would have caught the bug. I did not run the rest of the suite.

The logs confirm what my memory notes said. Both production images started on 2025-08-13 at 16:40Z, and `main-81d8ae42` includes the bad commit `c509d45e`. On Monday 2025-08-18 the scheduler sent no case close reminders, compared with 6 on 08-04 and 5 on 08-11.

I left alone the separate `TypeError` in `case_close_reminder` when `triage_at` is null. It is unrelated to this bug.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18