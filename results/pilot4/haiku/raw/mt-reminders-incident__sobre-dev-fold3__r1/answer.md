**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving. No reminder settings changed.
- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (1 for Monday) with `calendar.MONDAY` (0). The check was never true, so both weekly reminders were suppressed. Before commit `c509d45e` (a refactor that moved the check into this helper), the code used `isoweekday() == 1`, which was correct.
- **Deploy:** image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC. Commit `81d8ae42` contains `c509d45e`. The last Monday reminders were sent on 2025-08-11, under the earlier image. No reminders were sent on 2025-08-18 or later in the logs.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the original code and passes with the fix.
- **Secondary error:** `case_close_reminder` raised a `TypeError` every evening because some Triage cases have a null `triage_at`. The job now counts from `created_at` when `triage_at` is missing. Tests cover the fallback and the preference for `triage_at`.
- **Likely source of null `triage_at`:** the Slack reopen button sets Triage directly and skips the flow that stamps `triage_at`. This is inferred from the code; the logs don't record case IDs, so it is unconfirmed.
- **Open items:** the reopen path is unchanged. The stable reminder still skips cases with a null `stable_at` rather than using the `created_at` fallback.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at