**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check.

- **Before:** `date.today().isoweekday() == 1`. `isoweekday()` numbers Monday as 1.
- **After:** the new helper `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31` compares `isoweekday()` to `calendar.MONDAY`. `calendar.MONDAY` is 0, because the `calendar` module counts Monday as 0 (its weekday numbering is 0–6).
- **Effect:** `isoweekday()` returns 1–7 and never 0, so the check is never true. Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) skip the send every day, with no error. The daily triage reminder doesn't use the helper, so it's unaffected.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`.
- It started at 2025-08-13T16:40Z on both the scheduler (`scheduler-mhtsgqwwx-q5q2n`) and the web pods.
- It is the commit "fix(case): exclude resolved_by in update (#6183)", dated 2025-08-12. Its history contains `c509d45e`, so the refactor shipped along with it.
- The previous image, `main-b05613b5` (running since 2025-07-30T17:10Z), predates the refactor.

**Log evidence:**
- Close reminders were sent on Monday 07-28 (4), 08-04 (6) and 08-11 (5), all before the deploy.
- None were sent on Monday 08-18, the first Monday after it.
- The 08-18 stack trace now points at line 47 of `case_close_reminder`; in the 07-28 and 07-30 traces the same line was 43. That matches the refactor adding lines to the file.

**Unrelated noise:** the scheduler logs `unsupported operand type(s) for -: 'datetime' and 'NoneType'` on every daily run, including before the deploy. In `case_close_reminder` that's `case.triage_at` being None for some cases. It's caught and logged per case, and it predates this regression, so it isn't causing the missing reminders. `case_stable_reminder` already guards `stable_at`, and the stable-reminder errors only appear in the early-August logs, from before commit `32fa810f` ("not all cases have a stable_at date") reached production.

**Suggested fix, when you want it:** make the helper compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. A small test for `_is_reminder_day()` on a known Monday would stop this recurring. I haven't changed any code.

----- next turn -----

The Monday reminders are fixed, and there's a regression test for it. I haven't committed anything.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides now count Monday as 0, so the check is true on Mondays.
- **Test:** the new `tests/case/test_case_scheduled.py` patches today's date and checks `_is_reminder_day()` for each day of a week. It expects true on Monday 2025-08-18 and false on the other six days.
- **Verification:** all 7 cases pass with the fix. With the fix stashed, the Monday case fails, so the test would have caught the original bug. I only ran this new test file, not the full suite.

The test covers the helper, not the two reminder jobs. They both call the helper, but nothing checks that they send on a Monday. I didn't add that because it would need mocked database and messaging code.

The `triage_at` None errors in the scheduler logs are still there. `case_close_reminder` catches and logs them per case, so I left them alone.

----- next turn -----

The close reminder job no longer raises the TypeError. A case with no `triage_at` now counts its age from `created_at`, so it still gets its weekly reminder. I haven't committed anything.

**Cause:** `triage_at` is a nullable column (`case/models.py:97`). It is only filled in by `case_triage_status_flow` in `case/flows.py`, and only when that flow runs. Any case sitting in `triage` status that never went through the flow has `triage_at = NULL`, and `datetime.utcnow() - case.triage_at` then fails. From the repo and logs alone I can't tell which cases they are. Cases that predate the column are one candidate, and cases created directly in triage are another. If you want to know which, check the database for triage cases with a NULL `triage_at`.

**Fix:** in `src/dispatch/case/scheduled.py`, `case_close_reminder` now computes the span from `case.triage_at or case.created_at`. The job already loads `created_at`.

**Tests:** I added two tests to `tests/case/test_case_scheduled.py`.
- **Fallback:** a case with no `triage_at` that is 10 days old gets a reminder on a Monday, and one that is 2 days old doesn't.
- **Preference:** a case with a recent `triage_at` and an old `created_at` gets no reminder, so the fallback doesn't override a real `triage_at`.

With the source fix stashed, the fallback test fails, and the Monday-helper test also fails because that fix was stashed too. With the fix applied, all of `tests/case` passes (24 tests).

The tests call the registered job function directly, with the database and messaging calls replaced by stand-ins. `scheduler.add` doesn't return the function it decorates, so the tests look it up in `scheduler.registered_tasks`.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, that compared `isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the helper never returned true. Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, skipped every send without logging an error.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13T16:40Z and contains the refactor. The previous image, `main-b05613b5`, predates it.
- **Evidence:** close reminders went out on Mondays 07-28, 08-04 and 08-11. On Monday 08-18, the first Monday after the deploy, none were sent.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. A new test checks the helper for each day of a week. It fails against the buggy code and passes with the fix.
- **Second issue (the nightly TypeError):** `case_close_reminder` subtracted `case.triage_at`, which is NULL for triage cases that never went through the triage status flow. The job logged the error and skipped those cases every evening. This predates the regression. It now counts from `created_at` when `triage_at` is missing, with two tests. I couldn't tell from the repo and logs which cases have the NULL, so that is still unchecked.
- **State:** both fixes and the new test file (`tests/case/test_case_scheduled.py`) are in the working tree, not committed. `tests/case` passes (24 tests). Reminders for 08-18 and any later Mondays were never sent, so those assignees weren't reminded and nothing has re-sent them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at