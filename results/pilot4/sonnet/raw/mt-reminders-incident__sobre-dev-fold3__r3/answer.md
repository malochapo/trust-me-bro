**Recap**

- **Symptom:** From mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added `_is_reminder_day()`. It compares `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` use it, so neither sent anything. The daily triage reminder doesn't use it.
- **Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on the scheduler and API pods at about 2025-08-13 16:40 UTC. `c509d45e` is in `81d8ae42` and not in `b05613b5`.
- **Evidence:**
  - Close reminders were sent on Mondays 07-28, 08-04 and 08-11.
  - None were sent on 08-18, the first Monday after the rollout.
  - The logs end 08-20, so later Mondays aren't checked.
- **Fix:** `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`. The regression test checks it on real Mondays and non-Mondays.
- **Second issue (unrelated, older):** `case_close_reminder` logged a `TypeError` every evening because cases created directly in Triage never get `triage_at`. The subtraction then fails and the case is skipped. The job now counts from `created_at` when `triage_at` is missing, and there is a test for it. `case_stable_reminder` still skips cases with no `stable_at`.
- **State:** Both fixes and the tests are in the working tree, uncommitted. `tests/case` passes (24 tests). The fix is not deployed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at