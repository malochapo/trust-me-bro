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