**Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") broke the Monday check. It was shipped to production by the 2025-08-13 deploy of image `main-81d8ae42`.

**The bug.** The refactor moved the inline test `date.today().isoweekday() == 1` into a helper in `src/dispatch/case/scheduled.py:31`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. I ran it to check: `calendar.MONDAY` is 0, and 2025-08-18 (a Monday) gives `isoweekday() == 1`. The helper therefore returns False every day of the week.

`case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both gate on `q >= 1 and _is_reminder_day()`. Neither can ever send now. `case_triage_reminder` doesn't use the helper, so the daily triage reminders kept working.

**Evidence in the logs**
- **Before the deploy:** on Mondays 07-28, 08-04 and 08-11 at 18:00, `send_case_close_reminder` logged "Case close reminder sent to …" for 4 to 6 assignees each time.
- **After the deploy:** on Monday 08-18 at 18:00, `case_triage_reminder` logged a send to l.nguyen@example.com. No close or stable reminder was sent.
- **Which deploy:** the pods restarted twice, and the only version change was on 2025-08-13 at ~16:40Z. That restart brought up `main-81d8ae42` on both the scheduler and the API (it replaced `main-b05613b5`, deployed 07-30). `81d8ae42` is dated 08-12 14:47, after `c509d45e` at 14:05, so it includes the refactor. `b05613b5` predates it and still sent reminders on 08-04 and 08-11.
- **Line numbers:** the traceback line numbers moved from 43 to 47 in `case_close_reminder`, which matches the refactor's +4 lines. The refactor is the only commit in that window that touched the Monday condition.

**Unrelated noise in the logs.** `case_close_reminder` logs `TypeError: datetime - NoneType` for a triage case with no `triage_at`, and `case_stable_reminder` did the same for a case with no `stable_at` before 08-13. Those errors appear every day, including before the regression, and the per-case try/except keeps the loop going. The stable-case one is fixed in `32fa810f`. The `triage_at` one is still unguarded, so it's worth a separate fix. It isn't the cause of this outage.

**Fix, when you want it:** compare against `isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. A small test pinning a Monday date to True would stop this recurring. I haven't changed any code.

----- next turn -----

I fixed the Monday check in `src/dispatch/case/scheduled.py`. `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, the same as `calendar.MONDAY`, so the two now agree.

I added `tests/case/test_case_scheduled.py`, which pins dates to a Monday and to the days around it. Both Mondays (2025-08-11 and 2025-08-18) must return True, and the other days, Sunday included, must return False.

The new test file passes (8 tests). With the fix stashed and the old code back, the two Monday cases fail, so the test would have caught the regression. I ran only the new test file, not the full suite.

Nothing is committed or deployed, so the reminders stay off in production until this ships. The separate `triage_at is None` error in `case_close_reminder` is still unfixed.

----- next turn -----

Cases with no `triage_at` now get their weekly close reminder, counted from `created_at`. The fix is in `src/dispatch/case/scheduled.py`. All 12 tests in the new test file pass. I haven't run the rest of the suite, and nothing is committed or deployed.

**Cause of the TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at = NULL`. The job loads every case in `triage` status. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:595`), so a case that gets that status without going through that flow never has it. The Slack handlers in `src/dispatch/plugins/dispatch_slack/case/interactive.py` do set `case.status = CaseStatus.triage` directly. I didn't trace which path produced the cases in your logs. The error was caught per case, so the loop kept going, but those cases never got a reminder. The traceback was logged every evening, since the job runs daily.

**Fix.** The span is now computed from `case.triage_at or case.created_at`, and a comment explains why. `created_at` is already loaded by `get_all_by_status`, so there's no extra query.

**Tests.** I added four tests to `tests/case/test_case_scheduled.py`, driving the job with mocked cases on a pinned date:
- A case with no `triage_at`, created 10 days ago, gets a reminder on a Monday. This is the regression test. It fails on the old code with the `TypeError`.
- A case with no `triage_at`, created 2 days ago, gets no reminder.
- When `triage_at` is set, it takes precedence over `created_at`.
- A case with no `triage_at` gets nothing on a non-Monday.

The tests unwrap the job through `scheduler.registered_tasks`, because `scheduler.add` returns None and nothing else exposes the function.

I left `case_stable_reminder` alone. It skips cases with no `stable_at`, since a stable case with no timestamp has no meaningful date to count from. Tell me if you want it to fall back to another timestamp too.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the Monday reminders to close their long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday test into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The helper therefore returned False every day, and `case_close_reminder` and `case_stable_reminder` never sent anything. `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders kept working.
- **Deploy:** the scheduler and API pods restarted on 2025-08-13 at about 16:40Z and moved from image `main-b05613b5` to `main-81d8ae42`. That image's commit was made after `c509d45e`, so it contains the refactor.
- **Log evidence:** the Mondays 07-28, 08-04 and 08-11 each logged 4 to 6 "Case close reminder sent" lines. Monday 08-18 logged none, only a triage reminder to one assignee.
- **Fix:** the helper now uses `weekday() == calendar.MONDAY`. The regression test pins Mondays to True and the other days to False, and it fails on the old code.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at` empty. The field is only set in `case_triage_status_flow`, so cases that reach triage another way never get it.
- **Fix:** the job now falls back to `created_at`, so those cases get their weekly reminder. Four tests cover this, and the new test file has 12 tests that all pass. This error was independent of the outage and dates from before it.
- **Status:** both fixes are in the working tree, uncommitted and not deployed. Reminders stay off in production until they ship.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at