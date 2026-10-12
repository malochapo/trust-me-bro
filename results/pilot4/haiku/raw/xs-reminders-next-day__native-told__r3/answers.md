**Root cause:** the Monday check in `src/dispatch/case/scheduled.py` compares against the wrong constant. It is `date.today().isoweekday() == calendar.MONDAY` (line 33, in `_is_reminder_day()`). `calendar.MONDAY` is `0` in Python, since `calendar` numbers Monday as 0. `isoweekday()` numbers Monday as 1. I confirmed both values with a local Python check. The condition is therefore never true, so `case_close_reminder` and `case_stable_reminder` never send the weekly reminder. The daily `case_triage_reminder` has no weekday gate, which is why those still arrive.

**Commit:** `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced the literal `== 1` with `_is_reminder_day()`, and that is where the constant mismatch was introduced.

**Deploy that shipped it:** `main-81d8ae42`, rolled out 2025-08-13 16:40 UTC to the web pod (`api.log:13201`) and the scheduler pod (`scheduler.log:18851`). `81d8ae42` contains `c509d45e`. The previous scheduler build, `main-b05613b5` from 2025-07-30, does not.

**Evidence in the logs:** Monday 2025-08-11 shows "Case close reminder sent" lines. Monday 2025-08-18 shows none, and the stable reminder ran with no errors. That matches the report.

**Other things in the logs, not the cause:**
- `case_stable_reminder` raised `NoneType` errors on every run from 2025-07-28 to 2025-08-12. Commit `32fa810f` (2025-08-11) fixed that, and it shipped in the same `81d8ae42` deploy. Those errors were per-case and did not stop other cases.
- `case_close_reminder` still has no `triage_at is None` guard, so it logs per-case `TypeError`s (for example `scheduler.log:25269` on 2025-08-18). It is caught per case and does not block the other reminders, but it is worth fixing alongside the weekday bug.

I have not changed any code. I saved the finding to the memory directory, in `case-weekly-reminder-monday-bug.md` with an index line in `MEMORY.md`.

----- next turn -----

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