The Monday reminder gate is fixed in the working tree, with a regression test. I haven't committed it, since you didn't ask for a commit.

**The bug:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced it, and it shipped in `main-81d8ae42` on 2025-08-13. The scheduler log shows case close reminders went out on Monday 2025-08-11 and none on 2025-08-18.

**The fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.

**The test:** `tests/case/test_case_scheduled.py` checks the gate for each day of one week. On the original code the Monday case fails, and it passes with the fix.

**Test run:** the full suite gives 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They fail the same way with my change stashed, so they predate it.

**Left out of scope:** the logs show a daily `TypeError` in `case_close_reminder` when `triage_at` is `None`. That job has no guard for it, unlike the stable reminder. It is unrelated to the weekday bug, so I did not change it. It is noted in the memory file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18