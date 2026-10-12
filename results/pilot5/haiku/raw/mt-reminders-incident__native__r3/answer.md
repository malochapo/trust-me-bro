## Recap: weekly reminders not sent after the 2025-08-13 deploy

**Symptom:** Since mid-August, assignees didn't get the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into a helper. The helper compared `date.today().isoweekday()`, which is 1-based (Monday = 1), against `calendar.MONDAY`, which is 0-based (Monday = 0). The comparison was never true, so both weekly reminders were suppressed. The daily triage reminder has no weekday check, so it was unaffected.

**Deploy:** Image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC, and it contains `c509d45e`. The Monday 2025-08-11 run, before the deploy, still sent reminders. The Monday 2025-08-18 run did not. I inferred the deploy from pod logs; I did not check a deploy record.

**Fix (uncommitted):** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` fails on the old check and passes on the fix.

**Side issue, fixed (uncommitted):** `case_close_reminder` logged a `TypeError` every evening. It subtracted `case.triage_at` from `utcnow()`, and `triage_at` was NULL for some triage cases. The migration that added the column didn't backfill rows, and the Slack reopen button sets Triage without stamping `triage_at`. The job now counts from `created_at` when `triage_at` is missing, and a test covers that. I haven't confirmed which path produced the NULLs in production data.

**Not changed:** the reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py` still bypasses the triage transition flow.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at