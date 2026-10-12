**Root cause:** the Monday check compares against the wrong constant. `calendar.MONDAY` is `0` in Python, but `date.isoweekday()` returns `1` for Monday. So `_is_reminder_day()` is always `False`, and the weekly close and stable reminders never send. The daily triage reminders don't use that check, which is why they still arrive.

**Where it lives:** `src/dispatch/case/scheduled.py`, lines 31–33:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

It's used by `case_close_reminder` (line 49) and `case_stable_reminder` (line 95).

**Commit that introduced it:** `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). The original code was `date.today().isoweekday() == 1`. The refactor replaced the literal `1` with `calendar.MONDAY`, which is wrong by one.

**Deploy that shipped it:** the production restart on 2025-08-13 at about 16:40 UTC. Both the scheduler (`scheduler-mhtsgqwwx-q5q2n`) and the web pod (`web-5dkmr9s9s-xxktx`) came up then, and the scheduler log shows no close reminders after that. This is inferred from the restart timing. The repo has no deploy record, and the `8f1c999f` "deployment notes" commit is only a template generator. Commits merged before the restart include `c509d45e` (2025-08-12 14:05 PDT) and `81d8ae42`. `3d3bf623` is after it.

**Log evidence:**
- Monday 2025-08-04 and Monday 2025-08-11 both sent close reminders (6 and 5 sends).
- Monday 2025-08-18 sent none.
- Triage reminders went out every day through 2025-08-20.
- The `scheduler.log` close-reminder sends stop after 2025-08-11, the last Monday before the 08-13 restart.

**Fix (not applied, per your instruction):** either `date.today().weekday() == calendar.MONDAY` or `date.today().isoweekday() == calendar.MONDAY + 1`. The first is cleaner. Add a test that pins a known Monday. The reminders for 2025-08-18 through today were missed, and they won't be backfilled automatically.

I also saved this to memory in `case-weekly-reminder-regression.md` and added an index line to `MEMORY.md`.

----- next turn -----

Saved. The findings are in `memory/case-weekly-reminder-regression.md`, with an index line in `MEMORY.md`. Nothing in the repo was changed.

Tomorrow's session should pick up with:

- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It is always false, so the weekly close and stable reminders never send. Daily triage reminders are unaffected.
- **Introduced by:** `c509d45e` (Jordan Lee, 2025-08-12), which replaced the original literal `1`.
- **Deploy:** the production restart on 2025-08-13 at about 16:40 UTC. This is inferred from the log restarts, not from a deploy record.
- **Open questions:**
  - Confirm the exact release range with whoever runs deploys.
  - Decide whether to resend the reminders missed since 2025-08-18.
- **Next steps:** apply the fix (`date.today().weekday() == calendar.MONDAY` is the cleaner form), add a test pinned to a Monday, and run the test suite.

----- next turn -----

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