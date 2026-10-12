## Recap

**Incident:** Since the 2025-08-13 deploy, assignees have not received the weekly Monday reminders for long-running triage and stable cases. The daily triage reminder was unaffected because it has no weekday gate.

**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was always false, so both weekly jobs skipped every send. The check was written as `== 1` before commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"), which replaced the literal with `calendar.MONDAY`.

**Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` started on the scheduler at 2025-08-13 16:40 UTC. That commit contains `c509d45e`. The previous image, `main-b05613b5`, predates the refactor.

**Fix:** `weekday()` replaces `isoweekday()`, so the comparison uses the same 0-based numbering as `calendar.MONDAY`. Regression test: `tests/case/test_scheduled.py::test_is_reminder_day` covers all seven days of a week and fails on the old code for Monday.

**Secondary issue:** `case_close_reminder` logged a TypeError each evening from 2025-08-13 onward. The job subtracted `case.triage_at` from the current time, and `triage_at` was NULL for at least one triage case. The per-case `try/except` kept the job running, but that case never got a close reminder. The fix counts from `case.created_at` when `triage_at` is missing. Tests: `test_case_close_reminder_without_triage_at` covers an old case with no `triage_at` (sent) and a recent one (not sent).

**Open items:**
- **Cause of the NULL `triage_at` is not confirmed.** The logs don't include a case ID. Two plausible sources: cases from before `triage_at` was added in 2022 with no backfill, and the Slack reopen button (`reopen_button_click`, `plugins/dispatch_slack/case/interactive.py:1427`), which sets `status = triage` without going through the triage flow. The reopen path is not fixed.
- **First missed Monday is inferred, not observed.** The logs contain no send records. I took the first Monday after the 08-13 deploy from the deploy time and the code.
- **Uncommitted.** The weekday fix, the `created_at` fallback, and the new tests are in the working tree only.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```