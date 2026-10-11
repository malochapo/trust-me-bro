In my earlier answer I said I couldn't confirm which build contained the bad commit. I had missed the kubelet "Started container" lines in both logs, which give the image tags. Here is the corrected recap.

**Weekly Monday reminders (the main outage)**
- **What happened:** commit `c509d45e`, a refactor, moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so it is never true.
- **Effect:** `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending. `case_triage_reminder` doesn't use the helper, so it kept working.
- **Deploy:** the image `registry.example.com/dispatch:main-81d8ae42` started on both the scheduler and the web pods at 2025-08-13 ~16:40Z. The previous image was `main-b05613b5`, running since 2025-07-30. `81d8ae42` is a descendant of `c509d45e` (12 Aug 14:47 vs 14:05 -0700), so it contains the bug. The old image does not.
- **Last good Monday:** 2025-08-11, with about 6 reminders sent. On 2025-08-18, none were sent, and the jobs ran in about 0.03–0.05 s instead of about 1.3 s.
- **Fix:** `_is_reminder_day()` now uses `weekday()`, with a regression test.

**Evening TypeError (separate issue)**
- **What happened:** `case_close_reminder` computed `utcnow() - case.triage_at`. Some cases in triage status have `triage_at` set to NULL. Likely reasons are that the column was added in 2022 without a backfill and that case creation doesn't set it. I haven't checked the database.
- **Effect:** each affected case logged the error and was skipped, so those cases never got a reminder. This predates the outage.
- **Fix:** the age is now counted from `triage_at or created_at`, with tests.

Neither fix is committed or deployed yet. Missed Mondays are not retroactively sent: 2025-08-18, 2025-08-25 and every Monday after that until the fix ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at