**Recap**

- **Weekday bug:** commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. The comparison is never true, so the weekly close reminders for long-running triage cases and stable cases stopped going out. The daily triage reminder doesn't use the helper, so it kept working.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` went onto the scheduler and web pods at 2025-08-13 16:40 UTC. It replaced `main-b05613b5`, which doesn't contain `c509d45e`.
- **First missed reminders:** Monday 2025-08-18. Reminders were sent on 07-28, 08-04 and 08-11, none on 08-18, even though the jobs ran. The 08-11 reminders went out before the deploy.
- **Fix:** `_is_reminder_day()` now compares `weekday()` with `calendar.MONDAY`. A regression test covers the helper and both reminder jobs.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is nullable. It is only set when a case transitions into triage, so cases created directly in triage have none. The job now falls back to `created_at`, and tests cover that. The error predates the weekday bug and appears in the logs from 07-28.
- **Not changed:** `case_stable_reminder` skips cases with no `stable_at` instead of falling back to `created_at`.
- **Status:** the changes are uncommitted. I ran only the new test file (15 passed), not the full suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at