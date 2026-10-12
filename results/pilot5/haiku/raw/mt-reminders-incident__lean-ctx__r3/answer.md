## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** Assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.

- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check was never true, so no weekly reminders were sent. The fix is `date.today().weekday() == calendar.MONDAY`.
- **How it shipped:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) introduced the mismatch. It reached production in deploy `main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update"), which the scheduler started at 2025-08-13T16:40Z. The previous deploy, `main-b05613b5`, predates the refactor.
- **Evidence:** "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6) and 08-11 (5). There are none on 08-18 or later, through the end of the logs on 08-20.
- **Evening TypeError:** `case_close_reminder` subtracts `case.triage_at` with no guard, and that field is NULL for some cases in triage. Cases can reach triage without `triage_at` when they are created directly in that status, because `service.create` skips the triage transition flow. The job now counts those cases from `created_at`. The error was logged nightly through 08-20 and was not limited to 08-12, which I had wrongly reported earlier.
- **Other errors:** The stable reminder's `stable_at` TypeError stopped after 08-12, when `32fa810f` shipped. It is not part of this incident.

**Current state:** The working tree has the weekday fix, the `created_at` fallback, and new tests in `tests/case/test_case_scheduled.py`. Those tests fail on the old code. `python -m pytest tests/case -q` passes 24 tests. Nothing is committed. The stable-case path still skips cases with no `stable_at`, which you may want to decide on separately.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at