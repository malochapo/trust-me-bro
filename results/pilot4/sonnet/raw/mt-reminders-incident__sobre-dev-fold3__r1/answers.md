**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) broke the Monday check. It was shipped to production by the deploy of image `main-81d8ae42` on 2025-08-13 at 16:40Z.

**What the commit changed**
- `src/dispatch/case/scheduled.py` used to test `date.today().isoweekday() == 1`.
- The refactor moved that into a helper, `_is_reminder_day()`, which tests `isoweekday() == calendar.MONDAY`.
- `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. I confirmed this in Python, and that 2025-08-18 has `isoweekday()` 1.
- The helper is therefore never true, so `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both stop sending.
- `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders kept arriving.

**Evidence in the logs**
- On the Mondays before the deploy (07-28, 08-04, 08-11), the 18:00 run logs several "Case close reminder sent to …" lines.
- On Monday 08-18, after the deploy, there are none. There are zero such lines from 08-18 to 08-20.
- The container image changed from `main-b05613b5` to `main-81d8ae42` on 08-13 at 16:40Z, in both the scheduler and the API.
- The traceback line numbers in `scheduled.py` shifted after that point, for example `triage_at` at line 43 before and line 47 after. That matches the helper and import being added.
- `c509d45e` is not an ancestor of `b05613b5`, so the earlier deploy didn't have it. It is an ancestor of `81d8ae42`.
- The deploy on 08-13 was the first production release to include the change, and the first Monday after it, 08-18, was silent.

**Unrelated noise**
- Since at least 07-28, `case_close_reminder` has logged `datetime - None` errors, because some triage cases have no `triage_at`. These are caught per case and don't stop the other reminders, so they are not the cause.
- The same error in `case_stable_reminder` stopped on 08-13, after `32fa810f` added the `stable_at` guard.

I haven't changed any code. The fix is to compare against 1 or use `calendar.MONDAY + 1`, for example `date.today().weekday() == calendar.MONDAY`. A small test for `_is_reminder_day()` on a known Monday would stop it recurring.

----- next turn -----

I fixed the Monday check and added a regression test. The new test passes with the fix and fails without it. I ran only that test file, not the full suite, and I haven't committed anything.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` returns 0 for Monday, which is what `calendar.MONDAY` is. Before, it compared `isoweekday()` (1 for Monday) against 0, so it was never true.
- **Test:** `tests/case/test_case_scheduled.py` patches `date.today()` for a full week starting Monday 2025-08-18. It expects `_is_reminder_day()` to be true on the Monday and false on the other six days. Reverting the fix makes the Monday case fail.

The fix only takes effect once it is deployed. Assignees will start getting the weekly reminders again on the first Monday after that.

----- next turn -----

The nightly TypeError is fixed. Cases with no `triage_at` now count their age from `created_at`, so they get their weekly close reminder. The new test file passes (10 tests), and the main new test fails if the fix is reverted. I haven't committed anything.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at` for every triage case. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py`). That flow runs on a new→triage or closed→triage transition. A case that never made one of those transitions has `triage_at = None`, so the subtraction raised the TypeError. The per-case `try/except` caught and logged it, and the case was silently skipped, so it never got its reminder.

I read `case/service.py` and `case/flows.py` to find this. I did not confirm how those particular cases were created.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at`. Cases that have a `triage_at` behave as before.

**Tests:** in `tests/case/test_case_scheduled.py`, I added three tests for `case_close_reminder`. They cover:
- a 10-day-old case with no `triage_at`, which now gets a reminder;
- a 2-day-old case with no `triage_at`, which doesn't;
- a case with a recent `triage_at` but an old `created_at`, which doesn't, so `triage_at` still takes priority.

`scheduler.add()` returns `None`, so the tests fetch the job from `scheduler.registered_tasks` and strip its decorators.

I left `case_stable_reminder` alone. It still skips stable cases that have no `stable_at`, because you only asked about the close reminder. Say if you want the same fallback there.

----- next turn -----

## Recap

**Weekday bug**
- Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`.
- The helper compared `isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so it was never true.
- The weekly close reminders for long-running triage cases and for stable cases stopped sending. The daily triage reminder doesn't use the helper, so it kept working.
- Production picked up the bug when image `main-81d8ae42` started on 2025-08-13 at 16:40Z, in both the scheduler and the API.
- Monday 2025-08-11 still sent reminders. Monday 2025-08-18 sent none, and there are none through 08-20.
- The fix is `date.today().weekday() == calendar.MONDAY`, with a parametrized test over a full week. The test fails if the fix is reverted.

**Evening TypeError**
- `case_close_reminder` computed `utcnow() - case.triage_at`.
- `triage_at` is only set on a new→triage or closed→triage transition. Triage cases that never made one have it as `None`, so the subtraction raised the TypeError. I didn't confirm how those particular cases were created.
- The per-case `try/except` logged the error and skipped the case, so those cases never got a reminder. The other reminders were unaffected.
- The job now counts from `triage_at or created_at`, with tests for old cases, recent cases, and `triage_at` taking priority.

**Status:** both fixes and the new test file `tests/case/test_case_scheduled.py` are in the working tree, uncommitted and undeployed. I ran only that test file, not the full suite. `case_stable_reminder` still skips stable cases with no `stable_at`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at