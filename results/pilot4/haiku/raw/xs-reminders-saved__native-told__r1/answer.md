Assignees stopped getting the Monday close and stable reminders because `_is_reminder_day()` compared `date.today().isoweekday()`, which counts Monday as 1, with `calendar.MONDAY`, which is 0. The comparison was always false. I changed it to `date.today().weekday() == calendar.MONDAY`, which is 0-based on both sides. The fix is uncommitted.

**Verification**
- The logs confirm it. Close reminders were sent on Monday 2025-08-11 (6 sends), and none on 2025-08-18.
- The scheduler changed from image `main-b05613b5` to `main-81d8ae42` on 2025-08-13 at 16:40 UTC. `main-81d8ae42` contains `c509d45e`.
- The deploy attribution is inferred from the scheduler restart. The repo has no deploy record, so confirm the release with whoever runs deploys.
- New regression test `tests/case/test_case_scheduled.py` checks the weekday for Mondays, including 2025-08-18, and non-Mondays. It fails on the old code for both Mondays and passes with the fix.
- `python -m pytest tests/case` passes (20 tests). The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail with my change reverted, so they predate it.

**Not done / needs your decision**
- Monday reminders from 2025-08-18 onward were not sent and are not backfilled. Tell me if you want them resent.
- Separately, `case_close_reminder` and `case_stable_reminder` log a `TypeError` (datetime minus None) for some cases, daily since 2025-07-28. That looks like a `triage_at` or `stable_at` of None. The per-case try/except keeps other cases going, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18