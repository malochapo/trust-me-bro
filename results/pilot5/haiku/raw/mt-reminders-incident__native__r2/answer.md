**Recap**

- **Symptom:** Weekly reminders for long-running triage and stable cases stopped after the 2025-08-13 deploy. The daily triage reminders kept going. Nobody changed the reminder settings.
- **Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday test into `_is_reminder_day()`. It compared `date.today().isoweekday()` (1 for Monday) with `calendar.MONDAY` (0). The check was never true, so both weekly branches were dead. The job logged nothing, so the failure was silent.
- **Deploy:** Image `main-81d8ae42` started on the `scheduler` and `web` pods at 2025-08-13 16:40 UTC. That commit contains `c509d45e`.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. A regression test (`tests/case/test_case_scheduled.py`) pins the helper to a known Monday and the surrounding days. It fails on the old code.
- **Missed reminders:** The Monday sends on 2025-07-28, 08-04, and 08-11 all happened, before the deploy. The first missed Monday was 2025-08-18.
- **Evening TypeError (separate issue):** `case_close_reminder` subtracted `case.triage_at` without a null check. Triage cases that never went through the triage transition (`src/dispatch/case/flows.py:595`) have it NULL, so the job raised `TypeError` and skipped those cases. The fix uses `case.triage_at or case.created_at`, and a test covers the fallback. The test fails on the old code. I did not check production data, so I don't know how many cases were affected.
- **Test status:** 365 passed, 4 skipped. The 8 failures are in the AI service, database filter, and entity tests, and they fail on the original code too.
- **Not committed:** The changes are in the working tree.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```