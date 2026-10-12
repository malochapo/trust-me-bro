Weekly case reminders are fixed. The new tests pass with the fix and fail without it (3 failures against the old code).

**Cause:** commit `c509d45e` ("share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`. It compared `date.isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The check was therefore never true on any day, so `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending.

**Evidence in the logs:** reminders went out on Monday 2025-07-28, 08-04 and 08-11. The 08-12 commit first reached production in the `main-81d8ae42` rollout on 2025-08-13 at 16:40 UTC. On 08-18 the triage and stable reminder jobs ran at 18:00 but sent nothing.

**Fix:** in `src/dispatch/case/scheduled.py` I replaced `calendar.MONDAY` with a `MONDAY = 1` constant and a comment explaining the numbering. I also removed the now-unused `calendar` import.

**Test:** `tests/case/test_case_scheduled.py` checks that `_is_reminder_day()` is true only on Monday. It also checks that both reminder jobs send on a Monday and not on a Tuesday for a case that is over a week old.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18