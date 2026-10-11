**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The comparison is never true, so both weekly jobs (`case_close_reminder` and `case_stable_reminder`) silently stopped sending.
- **Deploy:** the rollout on 2025-08-13 at about 16:40 UTC moved scheduler and API from image `main-b05613b5` to `main-81d8ae42`. `81d8ae42` includes the refactor and `b05613b5` does not.
- **Timeline:** close reminders went out on Monday 2025-08-04 (6) and 2025-08-11 (5). On Monday 2025-08-18 none were sent. The 11th was before the deploy, so 2025-08-18 is the first miss.
- **Evening TypeError:** some triage cases have no `triage_at`, because only the triage status flow sets it. `datetime.utcnow() - case.triage_at` then fails and that case is skipped.
- **Fixes (uncommitted):**
  - `_is_reminder_day()` now uses `weekday()`.
  - The close reminder falls back to `created_at` when `triage_at` is missing.
  - Regression tests are in `tests/case/test_case_scheduled.py`, and all 30 tests in `tests/case` pass.
- **Open item:** `case_stable_reminder` still silently skips stable cases without `stable_at`.
- **Catch-up:** reminders missed on 2025-08-18 and later Mondays are not sent retroactively. The next Monday after the fix ships will cover them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at