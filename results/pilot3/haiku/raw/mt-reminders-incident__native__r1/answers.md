**Root cause:** the weekly Monday check is always false. Commit `c509d45e` moved the check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's calendar week starts at Sunday = 6, Monday = 0). I confirmed both values in the sandbox's Python. The original code compared against the literal `1`, which was correct. The refactor silently broke it.

The helper is used by both `case_close_reminder` (line 49) and `case_stable_reminder` (line 95), so both weekly reminders stopped. `case_triage_reminder` doesn't use the helper, so the daily triage reminders kept working, which matches what you're seeing.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, started 2025-08-13 16:40 UTC on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` (and the web pod at 16:40 too). It is the only deploy in the window that contains the change. `81d8ae42` (`fix(case): exclude resolved_by in update (#6183)`) has `c509d45e` as an ancestor, via `7c446bd6`. The refactor was committed 2025-08-12 14:05 -0700. The previous image, `main-b05613b5`, was deployed 2025-07-30.

**Evidence from the logs:**
- Mon 2025-08-04 (before the deploy): 6 "Case close reminder sent" lines.
- Mon 2025-08-11 (still on `b05613b5`): 5 close-reminder sends.
- Mon 2025-08-18 (after the deploy): 0 close-reminder sends, while 1 triage reminder went out.

**Side note, not the cause:** `case_close_reminder` still logs a `TypeError` on `case.triage_at` being `None` (line 47) on every run through 08-16. The per-case `try/except` contains it, so it doesn't stop other reminders, but it's worth a look.

No code changed. The likely fix is to compare against `1` (or `calendar.MONDAY + 1`), with a test for the Monday check. I haven't made that change; say the word and I'll do it.

----- next turn -----

The Monday reminder check is fixed, and there's a regression test for it. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `date.today().isoweekday() == calendar.MONDAY` became `date.today().weekday() == calendar.MONDAY`. `weekday()` is zero-based like `calendar.MONDAY`, so the comparison is now correct. The original code's literal `1` was also correct; `weekday()` keeps the named constant.

**The regression test** (`tests/case/test_case_scheduled.py`, new file): it pins `date.today()` in the scheduled module to a Monday, a Tuesday, and a Sunday, then asserts `_is_reminder_day()` returns True only on Monday. Against the old code, the Monday case fails (`assert False is True`), so it would have caught the bug. With the fix, all three pass.

**Test results:**
- `tests/case/` (including the new file): 21 passed.
- Full suite: 362 passed, 4 skipped, 8 failed.
- The 8 failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed the fix and ran them against the original code: the same 8 fail there too. They predate this change and are unrelated to it. I didn't investigate them further.

**Not covered:** the new test checks only the weekday gate, not the whole reminder path. It doesn't call `case_stable_reminder` end to end, because the decorator manages its own project and session context. An end-to-end test would be a reasonable follow-up.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there's a test for it. I haven't committed anything.

**What causes the TypeError:** `case_close_reminder` subtracts `case.triage_at` from `utcnow()`. For some triage cases `triage_at` is NULL, so the subtraction raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` logs it and moves on, so the other cases still get their reminders. The job runs daily, so one such case is enough to log the error every evening.

`triage_at` is only stamped by `case_triage_status_flow`, and two paths can leave a triage case without it:
1. **Case created in triage.** `case_service.create()` (`src/dispatch/case/service.py:205`) takes `status` from `CaseCreate` and saves it without running the triage flow. `CaseCreate` accepts a status.
2. **Transition into triage from Stable or Escalated.** The `(_, CaseStatus.triage)` branch in `case_status_transition_flow_dispatcher` (`src/dispatch/case/flows.py:762`) only logs a warning and never stamps `triage_at`.

The logs don't include case IDs or transitions, and I don't have database access, so I can't tell which of these produced the cases in your logs. To confirm, run this against the org schema in production: `SELECT id, status, created_at FROM "case" WHERE status = 'Triage' AND triage_at IS NULL;`

**The fix** (`src/dispatch/case/scheduled.py:47-51`): the job now counts from `case.triage_at or case.created_at`. The stable reminder is unchanged, so cases without `stable_at` still skip it. Say if you want that changed too.

**Tests** (`tests/case/test_case_scheduled.py`): two new tests.
- A triage case with no `triage_at` and `created_at` eight days ago gets the reminder on a Monday. I confirmed this test fails when the fallback is reverted, and passes with the fix.
- A case with `triage_at` one day ago and `created_at` thirty days ago gets no reminder, so `triage_at` still takes precedence.

The new tests call the raw job through `scheduler.registered_tasks`, because the decorator wrapper opens its own database connections.

**Full suite:** 364 passed, 4 skipped, 8 failed. The 8 failures are the same ones from before, and they fail without my changes too. `ruff` isn't installed here, so I didn't lint the changes.

**Still open:** the root cause is not fixed. Stamping `triage_at` on create and in the Stable/Escalated-to-triage branch would stop the cases from being created with no timestamp. I can make that change if you want it.

----- next turn -----

**Recap**

- **Weekly reminders stopped.** The weekly close and stable reminders for long-running cases stopped going out after the 2025-08-13 deploy. The daily triage reminders kept working.
- **Root cause.** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, which is 0. The check was always false.
- **Deploy.** Image `main-81d8ae42` started on 2025-08-13 at 16:40 UTC. It is the first deploy that contains the refactor. The Monday 2025-08-18 run sent no close reminders, while the earlier Mondays did.
- **Fix.** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` pins the date to Monday, Tuesday and Sunday, and it fails on the old code.
- **Evening TypeError.** `case_close_reminder` subtracted `triage_at`, which is NULL for some triage cases. Those cases can be created directly in triage, or moved into triage from Stable or Escalated, without the flow that sets `triage_at`. The fix counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the precedence of `triage_at`. The root cause in those paths is still open.
- **Tests.** The full suite has 8 failures that also occur without these changes. They are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`.
- **Not committed.** The changes are in the working tree.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at