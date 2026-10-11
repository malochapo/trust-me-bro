**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check.

- **The change:** the commit replaced `date.today().isoweekday() == 1` in `case_close_reminder` and `case_stable_reminder` with a new helper. The helper is `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31`, and it returns `date.today().isoweekday() == calendar.MONDAY`.
- **Why it never fires:** `calendar.MONDAY` is `0` (I checked), because the `calendar` module counts weekdays from Monday = 0. `isoweekday()` counts Monday = 1 through Sunday = 7, so it never returns 0. The helper therefore always returns `False`. The `q >= 1` check still passes, but the reminder branch is never reached.
- **Why it's silent:** nothing is logged and no error is raised. The daily `case_triage_reminder` doesn't use the helper, which matches what you're seeing.
- **Fix, when you want it:** compare against `calendar.MONDAY` using `date.today().weekday()`, or compare `isoweekday()` to `1`.

**Evidence from the logs:**
- Before the deploy, every Monday sent reminders: 07-28 (4 close reminders), 08-04 (6) and 08-11 (5).
- Monday 2025-08-18 sent none. The `case_close_reminder` and `case_stable_reminder` jobs ran at 18:00 and completed, but nothing was sent.
- Triage reminders were sent every day through 08-20.

**The deploy:**
- **Image:** the image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40:06Z. The web pod `web-5dkmr9s9s-xxktx` started on the same image at 16:40:07Z.
- **What it replaced:** `main-b05613b5`, which had been running since 2025-07-30T17:10Z.
- **Why it contains the bug:** `c509d45e` is an ancestor of `81d8ae42` and is not in `b05613b5`. It is the only change in that range to the reminder logic.
- **Weekday check:** 08-13 was the first weekday after the deploy and 08-18 the first Monday, so the failure first showed up on 08-18.

**Unrelated noise:** the old `main-b05613b5` image logged `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` for some cases. That is the missing `stable_at` and `triage_at` handling, which `32fa810f` (08-11) addressed. The `scheduled.py` line numbers in the Aug 18 log are 4 higher than in the old image's log, which fits the 4-line helper added by the new image. The error was still logged on 08-18 at `case_close_reminder:55`, so the `triage_at` case isn't fixed. It is caught per case, doesn't stop the loop, and didn't cause this outage.

I haven't changed any code.

----- next turn -----

I fixed the Monday check and added a regression test. All 26 tests in `tests/case` pass. I haven't committed anything.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both use Monday = 0, so the check can be true again. The bug was that it compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (0).

**Test:** the new file is `tests/case/test_case_scheduled.py`.
- **Helper check:** `_is_reminder_day()` must be true on a Monday and false on the other six days.
- **Reminder check:** `case_close_reminder` and `case_stable_reminder` are run on a frozen Monday with a 10-day-old case and must send a reminder. On the Tuesday they must not.
- **Why it would have caught the outage:** I reverted the source fix and re-ran the file. The three Monday cases fail without the fix: the helper check and one reminder case per job.

The scheduler decorator returns `None`, so the test finds each job in `scheduler.registered_tasks` and unwraps it. It won't send anything or touch the database.

The `triage_at` subtraction error from the earlier logs is separate and still unfixed. It is caught per case, so it doesn't block reminders for other cases. Should I fix that too?

----- next turn -----

The TypeError is fixed and has a test. All 27 tests in `tests/case` pass. Nothing is committed.

**Cause:** `case_close_reminder` did `datetime.utcnow() - case.triage_at`, and `triage_at` can be `None`. It is only set when a case goes through the triage status flow (`case_triage_status_flow` in `src/dispatch/case/flows.py`). Cases created directly in triage status never get it. The per-case `try/except` caught the error and logged it, so those cases never got a weekly reminder.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`.

**Test:** `test_close_reminder_counts_from_created_at_without_triage_at` in `tests/case/test_case_scheduled.py`. On a frozen Monday it uses two cases with no `triage_at`. The 10-day-old one gets a reminder, the 2-day-old one doesn't, and no error is logged. I reverted the source change and re-ran the file, and the new test fails without the fix.

**Stable job:** `case_stable_reminder` is unchanged. It already skips cases with no `stable_at`, so it doesn't log this error. Those cases get no reminder from that job. You only asked about the close reminder, so I left it. Should I make it fall back to `created_at` as well?

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added the helper `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (0), so it was never true. The close and stable reminder jobs ran every evening but never sent anything, and nothing was logged.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on 2025-08-13T16:40Z, on both the scheduler and web pods.
- **Evidence:** Mondays 07-28, 08-04 and 08-11 sent reminders. Monday 08-18 sent none. Daily triage reminders continued through 08-20.
- **Fix:** the helper now uses `date.today().weekday()`. The regression test checks the helper against every weekday and checks both jobs on a Monday and a Tuesday. It fails without the fix.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for cases created directly in triage. Only the triage status flow sets it. The job now falls back to `created_at`, and a test covers that.
- **Open items:** `case_stable_reminder` still skips cases with no `stable_at`, which I left alone. Nothing is committed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at