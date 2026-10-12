Fixed the weekly reminder bug and added a regression test. The changes are uncommitted in the working tree.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check was never true, so the weekly close and stable reminders stopped being sent. Commit `c509d45e` introduced it, and it shipped in `main-81d8ae42`. The logs agree: the last weekly sends were Monday 2025-08-11, and nothing went out on 2025-08-18.

**Fix:** one line, changed to `date.today().weekday() == calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` freezes `date.today()` to each day of a week and checks that only Monday counts as a reminder day. On the buggy code it fails for Monday and passes for the other six days. With the fix, all 7 pass.

**Full suite:** 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail identically on the clean tree, so they predate this change. I did not investigate them.

**Not done:** I did not commit. I also did not fix the separate `case_close_reminder` problem noted in memory: it has no `triage_at` None guard and logs a TypeError per affected case.

I updated the memory note with the fix and the first missed Monday.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18