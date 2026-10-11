**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. I haven't changed any code.

**The bug**
- The commit replaced the inline `date.today().isoweekday() == 1` in `src/dispatch/case/scheduled.py` with a new helper, `_is_reminder_day()`. The helper returns `date.today().isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is `0` (the `calendar` module counts weekdays from 0). `isoweekday()` returns 1–7, so it is never 0. I confirmed that Monday 2025-08-18 gives `isoweekday()` = 1.
- So `_is_reminder_day()` is always false. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) skip `send_case_close_reminder` every day, including Mondays.
- The daily triage reminder, `case_triage_reminder`, has no Monday check and was untouched, which is why it still arrives.
- The jobs still run and raise no error, so nothing in the logs flags the problem.

**Evidence in the logs**
- "Case close reminder sent" appears only on Monday 07-28 (4 sends), Monday 08-04 (6) and Monday 08-11 (5). There are none on Monday 08-18.
- The scheduler's 18:00 UTC run on 08-18 shows the jobs executing, with no close-reminder sends.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out on **2025-08-13 at about 16:40 UTC**.
- The kubelet "Started container" lines for both the scheduler (`scheduler-mhtsgqwwx-q5q2n`) and the web pod (`web-5dkmr9s9s-xxktx`) show this image. It replaced `main-b05613b5`, which had run since 07-30 17:10.
- `81d8ae42` descends from `c509d45e`, and that rollout was the first to include `case/scheduled.py` changes. The 28 commits between the two images touch that file only via `32fa810f` and `c509d45e`.
- The first Monday after the deploy was 08-18, which is the first missed reminder day. The 08-11 reminders still went out under the previous image.

The `stable_at` None fix (`32fa810f`) shipped in the same deploy. It is not the cause. It only removed the stable-case TypeError, and the log's daily error count drops from 2 to 1 on 08-13 as a result.

**Unrelated, pre-existing errors**
- The `case_close_reminder` TypeError (`triage_at` is None) appears every day before and after the deploy.
- The 08-15 database outage ("database system is starting up") is unrelated to the missing Monday reminders.
- The "No AI plugin enabled" warning for the weekly incident report is unrelated.

**Fix:** use `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`.

The `triage_at` None error still needs its own fix. That job's loop catches the exception per case, so a case with no `triage_at` skips its reminder on any day, including a Monday after the fix. I'd also add a test that fakes a Monday and checks the reminder is sent.

----- next turn -----

The Monday reminders are fixed and covered by a regression test. I haven't committed anything.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Python's `weekday()` and `calendar.MONDAY` both count Monday as 0, so they now agree.

**Test:** `tests/case/test_case_scheduled.py` is new.
- It checks `_is_reminder_day()` returns true only on a Monday, using 2025-08-18 and the days after it.
- It runs the real `case-close-reminder` and `case-stable-reminder` jobs on a Monday (the reminder must be sent) and on a Tuesday (it must not). The scheduler decorator doesn't return the function, so the test looks each job up by name in `scheduler.registered_tasks`.
- With my fix reverted, 3 of the 8 tests fail: the Monday check and both Monday job runs. With the fix in place, all 8 pass, and the whole `tests/case` directory passes (23 tests).

**Not fixed:** `case_close_reminder` still fails for triage cases whose `triage_at` is empty. The loop catches the error per case, so those cases get no reminder even on a Monday. Say if you want that fixed too.

----- next turn -----

`case_close_reminder` now counts from `created_at` when a triage case has no `triage_at`, and a new test covers it. Nothing is committed.

**Cause:** the daily traceback is `datetime.utcnow() - case.triage_at` with `triage_at` equal to None. `triage_at` is a nullable column, added in the 2022-08-01 migration `391f7c3e6992` with no backfill. It is only set by `case_triage_status_flow` in `case/flows.py`. So any case sitting in triage status that never went through that flow has no timestamp. That includes cases that were already in triage when the column was added, and any case put into triage another way. I couldn't see which cases are affected, because the logs don't name them. The error appears once per evening, so I'd expect one or a few such cases.

The loop catches the error per case, so the job kept running. Those cases never got a close reminder, even on a Monday. Cases with a timestamp were unaffected.

**Fix:** in `src/dispatch/case/scheduled.py`, the span is now `datetime.utcnow() - (case.triage_at or case.created_at)`.

**Test:** `test_close_reminder_falls_back_to_created_at_without_triage_at` in `tests/case/test_case_scheduled.py` uses two triage cases with no `triage_at`: one created 10 days ago, one 2 days ago.
- On a Monday, only the 10-day-old case gets a reminder.
- On a Tuesday, neither does.
- No exception is logged in either run.

With the source changes reverted, this test fails. With them in place, all 25 tests in `tests/case` pass.

**Stable-case job:** `case_stable_reminder` has the same gap. Commit `32fa810f` made it skip cases with no `stable_at`, so those cases get no weekly reminder. You only asked about the close job, so I left it alone. Falling back to `created_at` there would be a one-line change, but it's a behaviour choice for you.

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` (2025-08-12) refactored the inline Monday check into `_is_reminder_day()`. The helper compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1–7 and `calendar.MONDAY` is 0, so the check was never true. Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, silently skipped every day, with no error logged.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to the scheduler and web pods on 2025-08-13 at about 16:40 UTC. It replaced `main-b05613b5`. The log shows the last sends on Monday 2025-08-11 and none on Monday 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.
- **Second issue:** the evening TypeError came from triage cases with an empty `triage_at`. That column is nullable, with no backfill since 2022, and is only set when a case passes through the triage status flow. Those cases never got a weekly reminder. The job now counts from `created_at` when `triage_at` is missing.
- **Tests:** `tests/case/test_case_scheduled.py` covers the Monday and non-Monday cases for both jobs, plus the `created_at` fallback. `tests/case` passes (25 tests), and the new tests fail without the fixes.
- **Open items:** nothing is committed or deployed yet. `case_stable_reminder` still skips stable cases with no `stable_at`, which I left alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at