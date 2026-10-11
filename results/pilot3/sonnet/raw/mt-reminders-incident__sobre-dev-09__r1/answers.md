I've found the root cause and the deploy. I made no code changes.

**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) added a helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The refactor swapped `isoweekday() == 1` for `== calendar.MONDAY`. These use different numbering. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (I checked in Python). The helper is therefore never true, and `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) skip every case. They skip silently and log nothing, because the check is just an `if`. The daily triage reminder doesn't use the helper, so it kept working.

**Evidence from the logs:**
- "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6) and 08-11 (5), and never again.
- Monday 08-18 has 62 scheduler lines at 18:00 and no close reminders.
- Triage reminders go out every day through 08-20.

**Deploy:** scheduler pod `scheduler-mhtsgqwwx-q5q2n` started on image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40Z. The API pod `web-5dkmr9s9s-xxktx` started on the same image at the same time. This replaced `main-b05613b5` (deployed 2025-07-30), which doesn't contain `c509d45e`. `81d8ae42` does contain it. The stack-trace line numbers in `scheduler.log` also moved by 4 (51→55 and 43→47) after this deploy, which matches the added lines.

The first Monday after the deploy was 08-18, which was the first missed reminder day. The 08-11 reminders came from the old code.

**Unrelated noise:** `case.triage_at` is None on some cases, and that raises a `TypeError` in `case_close_reminder` every day. The stable-case version of this was fixed in `32fa810f`. It predates the outage, and the exception handler catches it, so it is not what stopped the reminders.

**Fix, when you want it:** change the helper to `== 1` (or `calendar.MONDAY + 1`), or use `date.today().weekday() == calendar.MONDAY`. `src/dispatch/incident/scheduled.py:229` still uses the literal `== 1`, so incident reminders are unaffected.

----- next turn -----

I fixed the bug and added regression tests. The new tests pass with the fix and fail without it. I ran only `tests/case/test_case_scheduled.py`, not the full suite, and I haven't committed anything.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use 0 for Monday. Before, `isoweekday()` returned 1 and `calendar.MONDAY` is 0, so the check was never true.

**Tests:** the new file is `tests/case/test_case_scheduled.py`. It has two parts:
- **Helper test:** it checks `_is_reminder_day()` for each day of a week starting Monday 2025-08-18 and expects true only on Monday.
- **Task test:** it runs `case-close-reminder` and `case-stable-reminder` with a case that has been in triage or stable for 10 days. It expects a reminder on Monday and none on Tuesday. The scheduler decorator doesn't return the task, so the test finds it in `scheduler.registered_tasks` and unwraps it.

With the fix stashed, three tests fail: the Monday helper case and the Monday case for each task. That is the same failure that stopped the reminders.

I didn't change `src/dispatch/incident/scheduled.py:229`, which still uses the literal `== 1`. The `ruff` formatter isn't installed here, so I couldn't run it on the new test file.

----- next turn -----

Cases in triage with no `triage_at` now get their weekly close reminder, counted from when the case was created. The new tests pass, and I haven't committed anything. I ran only `tests/case/test_case_scheduled.py`, not the full suite.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` is NULL for some cases in triage status. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), when a case moves into triage. `service.create` builds the case with `status=case_in.status` (`src/dispatch/case/service.py:205`). A case created directly in triage therefore never runs that flow and keeps a NULL `triage_at`. The `TypeError` was caught and logged for each such case, and the job skipped that case on every run. So these cases also lost their weekly reminders, apart from the Monday check bug. I didn't look at where those cases come from.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`.

**Tests:** I added three cases to `tests/case/test_case_scheduled.py`. A 10-day-old case with no `triage_at` gets a reminder on Monday, none on Tuesday, and logs no exception. A 2-day-old one gets no reminder even on Monday. With the fix stashed, 5 tests fail, including the new `created_at` ones.

I didn't touch `triage_at` itself. Setting it when a case is created in triage would stop the data gap at the source, but it's a separate change and doesn't backfill existing cases.

----- next turn -----

**Recap**

- **Symptom:** the weekly Monday reminders for long-running triage and stable cases stopped after 2025-08-11. The daily triage reminders kept working.
- **Root cause:** commit `c509d45e` (2025-08-12) was a refactor that moved the Monday check into `_is_reminder_day()`. It compared `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. The check was never true, so both weekly jobs skipped every case without logging anything.
- **Deploy:** the scheduler and API pods moved to image `main-81d8ae42` at 2025-08-13T16:40Z. That image contains `c509d45e`, and the previous image `main-b05613b5` does not.
- **First missed Monday:** 2025-08-18. The last reminders went out on 2025-08-11, under the old code.
- **Evening TypeError:** `case_close_reminder` computed `utcnow() - case.triage_at`. Cases created directly in triage never run the transition flow that sets `triage_at`, so it was NULL. The error was caught and logged, and the job skipped those cases. This is separate from the outage but also cost those cases their reminders.
- **Fixes (uncommitted, tests in `tests/case/test_case_scheduled.py`):**
  - The weekday check now uses `weekday()`.
  - The close reminder counts from `triage_at or created_at`.
  - The new tests fail without the fixes and pass with them. I ran only that test file, not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at