Recap for the incident report:

**Weekly case reminders stopped after the 2025-08-13 deploy.** Monday reminders for long-running triage and stable cases were never sent again. Daily triage reminders kept going out.

- **Cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The new code compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. A regression test (`tests/case/test_case_scheduled.py`) checks each day of the week and fails on the old line.
- **Deploy:** Image `main-81d8ae42` started on the scheduler at 2025-08-13T16:40:06Z. It contains `c509d45e`, and `main-b05613b5`, which ran before it, does not. I inferred the tag-to-commit mapping from the tag format and did not check the registry.
- **Impact:** The last close reminders went out on Monday 2025-08-11. Monday 2025-08-18 was the first missed weekly run, and the logs show no close reminders that day.

**Separate nightly TypeError in the close reminder job.** Cases in Triage with a NULL `triage_at` made `datetime.utcnow() - case.triage_at` raise. The per-case `try/except` logged it and skipped the case, so those cases never got a weekly reminder.
- **Fix:** The job counts from `case.triage_at or case.created_at`. Three tests cover it, and the fallback test fails without the fix.
- **Open:** I could not identify which cases have a NULL `triage_at`, and the cause is unconfirmed. Either the transition path into Triage skips setting it (`case_status_transition`'s `(_, CaseStatus.triage)` branch), or older cases were never backfilled when the column was added in 2022. Checking production for `status = 'Triage' AND triage_at IS NULL` would settle it.

**Test suite:** 369 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`, and they fail the same way without my changes.

**Not done:** Nothing is committed. The stable reminder still skips cases with no `stable_at`, which you did not ask me to change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at