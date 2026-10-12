**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the literal `1` with `calendar.MONDAY`. In Python, `calendar.MONDAY` is `0`, but `date.isoweekday()` returns `1` for Monday. The new helper therefore always returns False, so the weekly close and stable reminders never send.

- `src/dispatch/case/scheduled.py:31-33` defines `_is_reminder_day()` as `date.today().isoweekday() == calendar.MONDAY`. That is always False.
- `case_close_reminder` (line 49) and `case_stable_reminder` (line 95) both gate on `_is_reminder_day()`, so both weekly reminders are silenced.
- Before the refactor, the check was `date.today().isoweekday() == 1` (visible in the diff). `src/dispatch/incident/scheduled.py:229` still uses the literal `1`, which is why incident reminders are unaffected.
- The daily `case_triage_reminder` doesn't use this check, so it keeps working.

**The deploy:** `81d8ae42` ("fix(case): exclude resolved_by in update", #6183), deployed to production on 2025-08-13 at 16:40. The web container started with `registry.example.com/dispatch:main-81d8ae42`, and a new scheduler instance (`scheduler-mhtsgqwwx-q5q2n`) started at the same time. `c509d45e` is an ancestor of `81d8ae42` and is absent from the previous image (`main-b05613b5`, deployed 2025-07-30). So this deploy is the first to carry the bug.

**Timeline from the logs:**
- 2025-08-11 (Monday, old code): close reminders were sent to several assignees.
- 2025-08-18 (first Monday on the new code): no close or stable reminders were sent. The 18:00 run shows only the triage reminders.
- Daily triage reminders kept arriving, as you described.

**Secondary issues (not the cause of the Monday silence):**
- The stable-reminder `AttributeError` ("datetime - NoneType" on `case.stable_at`) ran daily from 2025-07-28 to 2025-08-12. Commit `32fa810f` added the `if case.stable_at:` guard and it stopped after that.
- `case_close_reminder` still reads `case.triage_at` without a guard (`scheduled.py:47`). It raises for some cases every day, including 2025-08-18 to 08-20. The per-case `try/except` contains the failure, but those cases never get a close reminder. The stable path got the guard in `32fa810f` and the triage path did not.

**Suggested fix (not applied):** compare against the `isoweekday()` scale, for example `date.today().isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`, which is 0-based. Add a guard for `triage_at` in `case_close_reminder` as well. A regression test that mocks Monday and asserts a reminder is sent would catch this.

No code changes made. The logs end on 2025-08-20, so I could not confirm the behavior on later Mondays, though the code path makes it deterministic.

----- next turn -----

I fixed the Monday check and added a regression test. The weekly close and stable reminders should go out on Mondays again. I did not commit anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides of the comparison are 0-based now. The old code compared the 1-based `isoweekday()` against `calendar.MONDAY`, which is 0, so it never matched.

**The regression test** (`tests/case/test_case_scheduled.py`): it patches `date` in the scheduled module and checks `_is_reminder_day()` for every day of the week, with Monday 2025-08-18 as the true case. I ran it against the old expression and the Monday case failed, which is the bug. Against the fix, all 7 cases pass.

**Test run:** `python -m pytest tests/case` against the local PostgreSQL gives 22 passed.

**Not changed:** the `case_close_reminder` loop still reads `case.triage_at` with no guard, so cases missing that timestamp raise each day and are skipped. The `try/except` contains the failure, and it is unrelated to the Monday silence, so I left it alone. If you want, the fix is the same `if case.triage_at:` guard that the stable path got in `32fa810f`.

----- next turn -----

The close reminder no longer raises. Cases with no `triage_at` now count from `created_at`, and they get their weekly reminder when it's due. I did not change where `triage_at` gets set, so the cases that hit this still skip that timestamp.

**What causes the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Cases in `triage` status sometimes have a NULL `triage_at`, and subtracting `None` raises the `TypeError`. The per-case `try/except` catches it, so the other cases still get processed, but the affected case never gets its reminder.

`triage_at` is only set by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Some paths put a case into triage without running that flow:
- The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly, with no transition flow.
- `case_service.update` (`src/dispatch/case/service.py:379-380`) sets the status directly. The API update endpoint then runs the transition flow as a background task, so that path is covered. I didn't check whether every caller of `update` does the same.

I could not query production data, so I can't say which of these produced the NULLs in your cases. The logs show one `TypeError` per evening from 2025-08-13 on, and two per day before that, when the stable job was also failing.

**The fix** (`src/dispatch/case/scheduled.py:46-48`):
```python
# cases that never recorded a triage time count from when they were created
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**Tests** (`tests/case/test_case_scheduled.py`): four cases for `case_close_reminder`. A NULL `triage_at` with an 8-day-old creation date sends. A NULL `triage_at` with a 3-day-old creation date doesn't. A set `triage_at` is used even when the creation date is older. When the fallback is removed, the first test fails with the same `TypeError`. The tests call the raw job function through the scheduler's registered tasks, with the database replaced by stubs.

`python -m pytest tests/case` passes: 26 tests.

**Things I noticed but didn't change:**
- `scheduler.add` in `src/dispatch/scheduler.py` returns `None`, so the module-level names `case_close_reminder` and the others are `None`. The jobs still run because the scheduler holds a reference in `registered_tasks`.
- I ran `black` on the changed files, but the original `scheduled.py` already failed black's check, so I left the file's existing formatting alone.

If you want the root cause handled too, the next step is to make the reopen button and any other direct triage assignments go through the triage flow, so `triage_at` is always set.

----- next turn -----

## Recap

**Weekly reminders silent since 2025-08-18.** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the literal `1` with `calendar.MONDAY`, which is `0` in Python. `date.isoweekday()` returns `1` for Monday, so `_is_reminder_day()` was always False. The weekly close and stable reminders never sent. The change reached production in deploy `main-81d8ae42` on 2025-08-13 at 16:40. The last Monday with reminders was 2025-08-11, under the old code. The daily triage reminders were unaffected. The fix changes `isoweekday()` to `weekday()`, and a regression test covers the weekday check.

**Evening TypeError from the close reminder.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some cases in triage have no `triage_at`, and subtracting `None` raised the `TypeError`. The per-case `try/except` contained it, so the rest of the batch still ran, but the affected cases got no reminder. `triage_at` is set only by the triage transition flow, and some paths enter triage without it, such as the Slack reopen button. I did not confirm which path produced the NULLs in production data. The fix counts from `created_at` when `triage_at` is missing. Tests cover both fallback and precedence.

**Not yet done:** the stable-reminder `None` guard from `32fa810f` is already in production, but the weekday fix and the `created_at` fallback are uncommitted in the working tree. The triage flow gap is still open.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at