**Root cause:** the weekly check in `src/dispatch/case/scheduled.py` compares the wrong number space, so it is never true on any day of the week.

- `_is_reminder_day()` (line 34) returns `date.today().isoweekday() == calendar.MONDAY`.
- `isoweekday()` numbers Monday as 1. `calendar.MONDAY` is 0. So the check can never pass.
- Before the refactor, the same check was written as `date.today().isoweekday() == 1`, which was correct.
- Both weekly paths use this helper: `case_close_reminder` (triaging cases) and `case_stable_reminder` (stable cases). The daily triage reminder (`case_triage_reminder`) doesn't use it, which is why it still arrives.

**Introduced by:** commit `c509d45e` by Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check." The diff replaced `== 1` with `_is_reminder_day()`, which uses `calendar.MONDAY`.

**Shipped by:** image `registry.example.com/dispatch:main-81d8ae42`. The scheduler and web pods both started on it at 2025-08-13 16:40 UTC, and the scheduler's previous image was `main-b05613b5`, which doesn't contain `c509d45e`. `81d8ae42` is a descendant of `c509d45e`, so the bad change is in that deploy.

**Log evidence:**
- Monday 2025-08-11 (before the deploy): 5 "Case close reminder sent" lines at 18:00 UTC.
- Monday 2025-08-18 (after the deploy): zero close reminders. Triage reminders still went out, and the incident close reminder ran normally.

**Side findings (not the cause):**
- `case_close_reminder` logs `unsupported operand type(s) ... 'NoneType'` on `case.triage_at` every day from 2025-08-16. It's caught per case, so it doesn't stop the job, but cases with no `triage_at` are skipped silently. The stable path got a None guard in `32fa810f`; the triage path has no equivalent.
- The scheduler log's stack traces show older line numbers than the current `HEAD`, so the logs don't match the current source exactly. The Monday mismatch above is still clear from the code and the logs.

No code was changed. The fix I would propose is `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`, plus a test that pins a known Monday. Want me to make that change?

----- next turn -----

The weekly reminders now work again: the Monday check uses `weekday()`, which matches `calendar.MONDAY`. I added a regression test, and it fails on the old logic and passes on the fix.

**The fix** (`src/dispatch/case/scheduled.py`, line 33):
```python
return date.today().weekday() == calendar.MONDAY
```
The old `isoweekday()` numbers Monday as 1 while `calendar.MONDAY` is 0, so the check was never true. `weekday()` numbers Monday as 0, matching `calendar`.

**The regression test** (`tests/case/test_case_scheduled.py`, new file): it pins `date.today()` to each day of the week through `_is_reminder_day()` and checks that only Monday returns True. I restored the fixed line after confirming that the old logic fails the Monday case.

**Test results** (`python -m pytest`, PostgreSQL running):
- `tests/case/test_case_scheduled.py`: 7 passed
- `tests/case`: 22 passed

I did not run the full test suite. The reminder jobs themselves (`case_close_reminder`, `case_stable_reminder`) are not directly covered; the test targets the helper that they call. The `triage_at` None-guard gap I noted earlier is still there and is out of scope for this fix.

Nothing is committed. The changes are in the working tree (`git status` shows the modified `scheduled.py` and the new test file), so you can review them before committing.

----- next turn -----

Cases with no `triage_at` now count from `created_at`, so they get their weekly reminder. The TypeError is gone, and there's a test for it.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from `utcnow()`. For some triage cases that column is NULL, so Python raises `datetime - NoneType`. The per-case `try/except` catches it and logs it, so the rest of the run continues, but the affected case never gets its reminder.

`triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`). Some code paths set `status = triage` without running that flow, so `triage_at` stays NULL:
- `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py:1419` assigns the status directly and never runs the flow.
- `case.create()` (`src/dispatch/case/service.py:205`) takes the status from the input and skips the flow, so a case created directly in triage never gets `triage_at`.

I couldn't confirm which of these produced the production rows. The logs have no case IDs and I have no database access. Nothing in the logs shows the TypeError before 2025-07-28, so it's not tied to the Monday refactor.

**The fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`):
```python
span = datetime.utcnow() - (case.triage_at or case.created_at)
```

**The tests** (`tests/case/test_case_scheduled.py`): they run the real job body against the test database and check which cases get a reminder.
- Missing `triage_at`, created 8 days ago: reminded.
- Missing `triage_at`, created 2 days ago: not reminded.
- `triage_at` set to 2 days ago, created 30 days ago: not reminded, so the existing timestamp still wins.

The first test fails when I put back the old `triage_at`-only line, and all 10 tests in the file pass with the fix. `python -m pytest tests/case` passes (25 tests).

I left the status-setting paths alone, since the request was the reminder fallback. Making `reopen_button_click` and `create()` run the transition flow would stop new cases from getting a NULL `triage_at`. Do you want that in this change?

Nothing is committed; the changes are in the working tree.

----- next turn -----

The incident recap is below. The six lines at the end are the fields you asked for.

**Summary**

- **What broke:** Weekly close and stable reminders stopped going out after 2025-08-13. Daily triage reminders kept working.
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check could never pass.
- **Introduced:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced `isoweekday() == 1` with the helper that uses `calendar.MONDAY`.
- **Shipped:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler and web pods on 2025-08-13 at 16:40 UTC.
- **Impact:** Monday 2025-08-11 (before the deploy) sent 5 case close reminders. Monday 2025-08-18 sent none. The reminder settings were never changed.
- **Fix:** `date.today().weekday() == calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` fails on the old logic and passes on the fix.

**Secondary issue:** `case_close_reminder` logged a TypeError every evening from 2025-07-28 (later 2025-08-16 for the close job). It came from subtracting a NULL `triage_at` from the current time. `triage_at` is only set by the triage transition flow, and some paths put a case into triage without it, such as the Slack reopen handler. The fix counts from `created_at` when `triage_at` is missing, and the tests cover that case. The status-setting paths themselves are not yet fixed.

**Status:** Both fixes are uncommitted in the working tree. The tests I added and the existing `tests/case` suite pass (25 tests).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at