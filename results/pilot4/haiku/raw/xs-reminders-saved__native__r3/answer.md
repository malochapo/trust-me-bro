The weekday bug is fixed and covered by a regression test. The reminder check was comparing against the wrong value for Monday, so the Monday case reminders stopped being sent.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). It never matched, so the close and stable case reminders stopped being sent on every day, not just Mondays. The logs agree: reminders went out on Monday 2025-08-11 under `main-b05613b5`, and none were sent after `main-81d8ae42` started on 2025-08-13.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` (new) covers:
- `_is_reminder_day()` returns true only on a Monday.
- The close and stable reminder jobs send on a Monday for a case that has waited more than a week.
- Those jobs send nothing on a Tuesday.

The Monday-send tests failed against the old code and pass with the fix. The job tests call the registered job bodies directly, so they need no database.

**Test results:** the case tests pass (26). The full suite has 8 failures: six in `tests/ai/test_ai_service.py` and one each in `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. All 8 also fail on the clean tree, so they predate this change.

**Not done:**
- Changes are uncommitted in the working tree.
- The Mondays already missed are not retried. Cases still waiting will get their reminder on the next Monday after this fix is deployed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18