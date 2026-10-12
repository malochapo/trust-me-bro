**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

- The refactor replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, which returns `date.today().isoweekday() == calendar.MONDAY`.
- `date.isoweekday()` numbers Monday–Sunday as 1–7. `calendar.MONDAY` is 0, because the `calendar` module numbers days 0–6.
- The comparison is therefore never true, on any day. The weekly branch in `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) never runs, and no exception is raised.
- The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why those still arrive.
- The fix would be to compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. I haven't changed any code.

**Log evidence (`scheduler.log`):**
- "Case close reminder sent to …" lines appear only on Mondays 07-28 (4 sends), 08-04 (6) and 08-11 (5).
- There are none on Monday 08-18, and none on any other day in the window.
- Both jobs still run daily at 18:00 through 08-20 and log their elapsed time, so nothing is crashing or unscheduled.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to production on 2025-08-13 at about 16:40Z.
- The kubelet "Started container" lines in both `scheduler.log` and `api.log` show the new scheduler and web pods starting at that time.
- `c509d45e` is an ancestor of `81d8ae42` and is not in the previous image, `main-b05613b5` (deployed 2025-07-30 17:10Z).
- The first Monday after the rollout (08-18) is the first missed reminder. The last successful one was 08-11, before the deploy.

**Unrelated noise:** both reminder jobs log `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` (a case with a null `triage_at` or `stable_at`). This was already happening on 07-28, so it isn't what stopped the reminders. The 08-11 commit `32fa810f` ("not all cases have a stable_at date") looks like a partial fix for it. The error is caught per case, so it never stopped the loop. It could still skip an individual case.

One more thing: the refactor commit is labelled as a no-op refactor, and nothing tests the Monday gate, which is how the wrong constant got through.

----- next turn -----

I saved the findings to memory, so a new session can pick this up from the note `weekly-case-reminder-bug.md`. It records:

- the root cause (`calendar.MONDAY` is 0 but `isoweekday()` returns 1–7);
- the culprit commit `c509d45e` and the deploy `main-81d8ae42` (2025-08-13 ~16:40Z);
- the proposed fix, which is not applied;
- the unrelated null-timestamp error.

I also added a pointer to it in `MEMORY.md`.

----- next turn -----

Monday reminders are fixed. The new tests pass with the fix and fail without it (3 of 6 fail on the old code). I ran only the new test file, not the full suite.

**Cause:** `_is_reminder_day()` compared `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0), so it was never true on any day. That silently stopped `case_close_reminder` and `case_stable_reminder`. Both ran at 18:00 daily and raised no error. `case_triage_reminder` doesn't use the helper, so it kept working.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`, in `src/dispatch/case/scheduled.py`.

**Test:** `tests/case/test_case_scheduled.py` does two things:
- It checks the helper is true only on a Monday.
- It runs both weekly jobs with a 15-day-old case and checks the reminder is sent on Monday 2025-08-18 and not on Tuesday 2025-08-19.

I checked the dates in the logs. The last sends were on Monday 2025-08-11. The `main-81d8ae42` image started on 2025-08-13, a Wednesday, so 2025-08-18 was the first Monday without reminders.

The null `triage_at` error in the logs is a separate issue, and I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18