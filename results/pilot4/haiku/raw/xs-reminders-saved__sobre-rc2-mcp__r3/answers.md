**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is `0` in Python. The condition is never true, so the weekly close reminder (`case_close_reminder`, line 49) and the weekly stable reminder (`case_stable_reminder`, line 95) never send. The daily triage reminder doesn't go through this check, which is why it still arrives.

**Introduced by:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced the inline `date.today().isoweekday() == 1` with the helper. The old code was correct; the refactor changed the constant. I confirmed `calendar.MONDAY == 0` and `isoweekday()` for a Monday is `1`.

**Shipped by:** `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)"), which contains `c509d45e`. The image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40 UTC for both the `web` and `scheduler` deployments (`api.log` and `scheduler.log`). The previous image, `main-b05613b5`, started on 2025-07-30.

**Log evidence:** "Case close reminder sent" appears on Mondays 2025-07-28, 08-04, and 08-11 (old image), and never again. Stable reminders also stop after the deploy. Triage reminders keep firing daily through 2025-08-20.

**Fix (not applied):** compare against `1` or use `calendar.MONDAY` with `.weekday()` instead of `.isoweekday()`. I didn't change any code. Also note that the function is now duplicated across commits, so a test covering the Monday case would catch this.

----- next turn -----

I saved the findings to memory so a new session can pick them up:

- `case-weekly-reminder-regression.md` in the project memory directory has the root cause, the commit and deploy, the log evidence, and the fix that's still pending.
- `MEMORY.md` now has a one-line pointer to it.

Nothing in the repo changed. The fix is still open: compare against `1`, or use `.weekday() == calendar.MONDAY`, and add a test for the Monday case. When you pick this up, re-check the line numbers first in case `src/dispatch/case/scheduled.py` has changed.

----- next turn -----

The Monday reminders were never sent because a refactor compared against `calendar.MONDAY`, which is `0`, while `isoweekday()` returns `1` for Monday. The fix is in and a regression test covers it. The changes are uncommitted in the working tree.

**Cause:** `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The original code compared `date.today().isoweekday() == 1`. The refactor changed it to `isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is `0` (Monday-first, 0-based), so the check was never true. Both `case_close_reminder` and `case_stable_reminder` call it, so both stopped. The daily triage reminder doesn't use this check and kept working, which is why the logs still showed sends.

**Evidence from the logs:**
- Close reminders went out on Monday 2025-08-11, before the bug commit.
- The API log shows the image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13. That image's history contains `c509d45e`.
- No case close or stable reminders were sent on Monday 2025-08-18, the first Monday after that deploy.

**Changes:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches.
- `tests/case/test_case_scheduled.py` (new): freezes `date.today()` and checks that Mondays return true and Tuesday through Sunday return false. The Monday cases fail on the buggy code and pass with the fix.

**Verification:**
- `python -m pytest tests/case`: 23 passed.
- Full `python -m pytest`: 367 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail with the fix reverted, so they predate this change and are unrelated. I did not investigate them further.

Reminders for Mondays already missed won't re-send automatically. Whether to notify those assignees is your call.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18