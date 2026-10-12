The weekly Monday reminders for long-running triage and stable cases are fixed, and a regression test covers the bug. I haven't committed anything.

**Cause:** Refactor `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It had been `date.today().isoweekday() == 1`. The refactor changed the right-hand side to `calendar.MONDAY`, which is `0` in Python's `calendar` module, while `isoweekday()` returns `1` for Monday. The condition never matched, so no weekly reminder has gone out since.

**Timeline from the logs:** The last close reminders were sent on Monday 2025-08-11, before the refactor shipped. The scheduler restarted on image `main-81d8ae42` on 2025-08-13, and that image contains `c509d45e`. The first Monday without reminders is 2025-08-18.

**Changes:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`, so both sides use the same zero-based numbering.
- `tests/case/test_case_scheduled.py` (new): checks that the helper returns true only on Monday for each day of a week, and separately checks Monday 2025-08-18 with `calendar.MONDAY`. I confirmed the tests fail when the buggy line is restored and pass with the fix.

**Verification:** `python -m pytest tests/case` passes (23 tests). I didn't run the full suite.

**Not done:** The scheduler log also shows `case_stable_reminder` raising `TypeError` on cases with `stable_at = None`, with a traceback at `scheduled.py:93`. That's a separate issue. The `if case.stable_at:` guard should cover it, so it's worth a look, but I didn't investigate it further. Nothing committed.

I couldn't load an earlier sobre session to check yesterday's notes, so this comes from the logs and git history alone. I recorded the finding with `sobre_session`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18