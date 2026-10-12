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