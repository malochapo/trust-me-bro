**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. It was shipped to production by the 2025-08-13 deploy of image `main-81d8ae42`.

**The bug**
- The refactor replaced `date.today().isoweekday() == 1` with a new helper `_is_reminder_day()`. The helper returns `date.today().isoweekday() == calendar.MONDAY` (`src/dispatch/case/scheduled.py:31-33`).
- `isoweekday()` numbers Monday as 1 and Sunday as 7. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0.
- So the helper never returns true on any day. `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both use it, so neither sends a reminder any more.
- The daily triage reminder (`case_triage_reminder`) doesn't use the helper. That is why those still arrive, and why nobody touched the settings.

**What the logs show**
- **Last weekly reminders:** "Case close reminder sent" appears on Monday 2025-08-04 and Monday 2025-08-11, with 4–6 recipients each, from the old `isoweekday() == 1` code on image `main-b05613b5`.
- **Missing on Aug 18:** There are none on Monday 2025-08-18, and none on any other day after the deploy. The jobs still run at 18:00 every day.
- **Deploy time:** The new image started at 2025-08-13T16:40Z on both the scheduler and the web pods. Tracebacks from the scheduler shift from `scheduled.py` line 43 to line 47, which matches the 4 lines the refactor added.
- **No errors from the broken check:** It fails silently. The stable job logs no error at all after 8/13, because `32fa810f` (shipped in the same deploy) fixed an earlier `stable_at` error.

**Other findings, not the cause of this**
- `case_close_reminder` has a separate bug that predates all of this. It subtracts `case.triage_at` without a `None` check, so it raises `TypeError` on cases with no `triage_at`. The exception is caught per case, so it only drops those cases.
- Before the 8/13 deploy, the same `None` error hit `case_stable_reminder` daily. Those cases were skipped as well.
- The deploy also included `bce2fca2` and `81d8ae42`, the resolved-by feature and its fix. I found nothing in them that touches reminders.
- I found no code or config path in the logs that would explain a scheduling problem. The scheduler ran normally, apart from a few database connection errors around 8/13–8/15.

I haven't changed any code. The fix would be to compare against `calendar.MONDAY + 1`, or more simply `date.today().weekday() == calendar.MONDAY`. A test covering a Monday date would have caught this.

----- next turn -----

I saved the findings to memory as `weekly-case-reminder-outage` and added a pointer to it in `MEMORY.md`. It records the root cause, the deploy, the suggested fix and the separate `triage_at` bug. It also notes that no code has been changed yet, so a new session can start from the fix.

----- next turn -----

I fixed the weekday bug, and the new tests pass with the fix. With the fix reverted, the two Monday cases fail, so they would have caught it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. That silenced the weekly close reminders for triage cases and the weekly reminders for stable cases. The daily triage reminder doesn't use the check, so it kept working.

**Fix:** the check now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks that `_is_reminder_day()` is true on Monday 2025-08-18 and false on a Tuesday and a Sunday. It also runs the real close and stable reminder tasks with the date mocked and confirms they send on a Monday and don't on a Tuesday.

**Log check:** I re-checked the logs. "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11 and never on 08-18. Image `main-81d8ae42` started on 2025-08-13T16:40Z in both the scheduler and the API.

I didn't touch the separate bug I noted earlier: `case_close_reminder` subtracts `case.triage_at` without a `None` check, so cases with no `triage_at` raise a `TypeError`. The per-case `try`/`except` catches it and logs it, so other cases still get their reminders. I haven't committed anything.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18