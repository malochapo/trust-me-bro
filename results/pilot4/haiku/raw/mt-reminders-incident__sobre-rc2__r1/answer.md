Recap:

- **Weekday bug:** commit `c509d45e` (Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` and compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so the weekly long-running reminders for triage and stable cases stopped. Daily triage reminders were unaffected.
- **Deploy:** `main-81d8ae42` started on both the API and scheduler pods on 2025-08-13 at 16:40 UTC. It is the first image that contains `c509d45e`. The previous image, `main-b05613b5`, does not.
- **Last good Monday:** 2025-08-11 at 18:00 UTC sent weekly close reminders. The first missed one was Monday 2025-08-18.
- **Evening TypeError:** `case_close_reminder` failed on cases in Triage with no `triage_at`. The likely path is the Slack reopen button, which sets Triage without running the triage flow. I have not confirmed this against production data.
- **Fixes (uncommitted):** `_is_reminder_day()` now uses `weekday()`, and the close reminder falls back to `created_at`. Both have regression tests. `python -m pytest tests/case` passes (20 tests). These changes are not deployed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at