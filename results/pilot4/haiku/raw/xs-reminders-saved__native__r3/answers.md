**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares two different numbering schemes:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`date.today().isoweekday()` returns 1 for Monday through 7 for Sunday. `calendar.MONDAY` is 0, because the `calendar` module numbers weekdays from 0. So the check is `1 == 0`, which is always false, and the weekly close/stable reminders never send. I confirmed both values in Python: `calendar.MONDAY` is 0 and `isoweekday()` for 2025-08-18 is 1.

The bug affects both paths that call it: `case_close_reminder` (long-running triage) and `case_stable_reminder` (stable cases). The daily `case_triage_reminder` doesn't use the helper, which is why those still arrive. The incident-side check at `src/dispatch/incident/scheduled.py:229` uses the literal `== 1` and is unaffected.

**The change that introduced it:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). The original code was `date.today().isoweekday() == 1`. The refactor moved it into the helper and replaced the literal `1` with `calendar.MONDAY`. That looks behavior-preserving but isn't.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out on **2025-08-13 at 16:40 UTC**. Both `web` (`api.log:13201`) and `scheduler` (`scheduler.log:18851`) started on that image. `81d8ae42` is a descendant of `c509d45e`, and it is the first image in the logs that contains the refactor. The previous image, `main-b05613b5`, started on 2025-07-30.

**Log evidence:**
- Monday 2025-08-11 (before the deploy): `Case close reminder sent to ...` lines for several assignees from `case_close_reminder`.
- Monday 2025-08-18 (after the deploy): no close reminders. `case_close_reminder` and `case_stable_reminder` run and return normally, and `case_triage_reminder` sends its daily messages as usual.

The current HEAD (`51546e13`) still contains the bug. I haven't changed any code.

**Suggested fix (not applied):** compare against the same numbering, for example `date.today().weekday() == calendar.MONDAY` or `date.today().isoweekday() == 1`. Then add a test that pins the reminder day to a Monday date, since none exists today.

----- next turn -----

I saved the findings to memory so tomorrow's session can pick them up:

- `memory/case-weekly-reminder-monday-bug.md` holds the root cause, the commit that introduced it, the deploy that shipped it, the log evidence, and the suggested fix.
- `memory/MEMORY.md` has a one-line pointer to that file.

The memory notes that nothing has been changed yet. Tomorrow's session should first check whether the fix has landed on HEAD before proposing it.

----- next turn -----

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