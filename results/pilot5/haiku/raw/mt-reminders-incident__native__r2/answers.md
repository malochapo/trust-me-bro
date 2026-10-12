The root cause is a bad comparison in the weekly-reminder refactor. It shipped to production in the deploy of `main-81d8ae42` on 2025-08-13 at 16:40 UTC. I haven't changed any code.

**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday test into a helper:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

The original check was `date.today().isoweekday() == 1`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is `0` (Python's calendar week starts at Sunday = 6, Monday = 0). I confirmed both values locally. So `_is_reminder_day()` is always False, and both weekly branches are dead:
- `case_stable_reminder` (line 95)
- `case_close_reminder` (line 49), which covers long-running triage cases

The daily `case_triage_reminder` doesn't call the helper, so it keeps sending. That matches what you're seeing.

**Deploy that shipped it:** `81d8ae42` ("fix(case): exclude resolved_by in update", 2025-08-12). `c509d45e` is an ancestor of it. In `api.log` and `scheduler.log`, the `web` and `scheduler` pods started on image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40 UTC, replacing `main-b05613b5`. The previous image didn't contain `c509d45e`.

**Evidence in the logs:**
- Weekly sends on Mondays 2025-07-28 (4), 08-04 (6), and 08-11 (5) all happened, all before the deploy.
- The first Monday after the deploy was 2025-08-18. The `case-stable-reminder` run that day finished with no error and no "reminder sent" lines. The same is true for the weekly triage reminder path. The failure is silent, which is why nothing alerted.

**Related but separate:** the stable-case reminder logged a `NoneType` error on every daily run from 07-28 to 08-12, because `case.stable_at` can be null. That was fixed by `32fa810f` (2025-08-11), which was deployed with `81d8ae42`, so those errors stop after 08-13. That fix is not the cause of the missing reminders. Separately, `case_close_reminder` still logs a `triage_at` NoneType error once a day through 08-20. It's caught per case, so it only skips that case. It's worth a follow-up but isn't this regression.

**Fix options (not applied):** either restore `date.today().isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY` (`weekday()` is the 0-based form that matches `calendar.MONDAY`). A test that pins `_is_reminder_day()` to a known Monday would catch this class of mistake.

----- next turn -----

The fix is in, and the regression test is added. The suite has 8 failures, and the same 8 fail on the original code, so they predate this change.

**The fix** (`src/dispatch/case/scheduled.py:33`):

```python
return date.today().weekday() == calendar.MONDAY
```

`weekday()` is 0-based, like `calendar.MONDAY`. The old `isoweekday()` is 1-based, so the comparison could never match.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it patches `date` in the scheduler module and checks `_is_reminder_day()` on a known Monday (2025-08-18), the Sunday before and Tuesday after it, and the next Monday (2025-08-25). I confirmed it fails on the old code (2 failures, both Monday cases) and passes with the fix (4 passed).

**Full suite** (`python -m pytest`, PostgreSQL running locally): 363 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). I stashed my changes and ran those three files on the original code, and the same 8 failed there.

Nothing is committed. The working tree has the one-line change in `scheduled.py` and the new test file.

----- next turn -----

The `case_close_reminder` TypeError is fixed, and the job now falls back to the case's creation time when `triage_at` is missing. The new test passes, and the full suite shows the same 8 failures as before (in AI service, database filter, and entity tests), which also fail on the original code.

**Cause:** `triage_at` is only set by the triage transition in `src/dispatch/case/flows.py:595`. A case that reached triage without that transition keeps `triage_at` as NULL. The job then computes `datetime.utcnow() - case.triage_at`, which raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` catches it, so the job logs it and skips that case. I didn't check the production database to see how many cases are affected, so the exact count is unknown.

**Fix** (`src/dispatch/case/scheduled.py:47-50`):

```python
triaged_at = case.triage_at or case.created_at
span = datetime.utcnow() - triaged_at
```

**Test** (`tests/case/test_case_scheduled.py`): it builds a triage case with `triage_at=None` and calls the job body with the scheduler's `_is_reminder_day` stubbed to True.
- Created 8 days ago: expects one reminder. It fails on the old code and passes with the fix.
- Created 3 days ago: expects no reminder. It passes on both, as a boundary check.

Two notes on the test:
- `scheduler.add` returns `None`, so `case_close_reminder` is `None` at module level. The test looks the job up by name in `scheduler.registered_tasks` and unwraps it. I didn't change the scheduler to make this easier.
- The test file also still includes the `_is_reminder_day` Monday test from before.

Nothing is committed. The working tree has the change in `scheduled.py` and the new test file.

----- next turn -----

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