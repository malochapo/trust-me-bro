**Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into a helper that compares the wrong constant:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday (ISO numbering, 1–7), but `calendar.MONDAY` is 0 (I confirmed both in Python). So `_is_reminder_day()` is always False, and the `q >= 1 and _is_reminder_day()` guard in `case_close_reminder` (triage) and `case_stable_reminder` (stable) never passes. Before the refactor, the code had `date.today().isoweekday() == 1`, which was correct. Both weekly reminders share this helper, which is why both stopped. The daily triage reminder (`case_triage_reminder`) has no weekday check, so it still runs.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13 16:40:06Z (`scheduler.log:18851`). Commit `81d8ae42` ("fix(case): exclude resolved_by in update (#6183)") contains `c509d45e`, so the refactor is in that image. The web pod got the same image at 16:40:07Z (`api.log:13201`).

**Confirmation in the logs:**
- Monday case reminders were sent on 07-28, 08-04 and 08-11, from the older image `main-b05613b5` (deployed 07-30) and the code before the refactor.
- No case close or stable reminders were sent after the 08-13 deploy. The first Monday after it, 08-18, has none.
- The daily triage reminders kept going, as you described.

**Something else you should know:** the scheduler also logs a daily `TypeError` from `case_close_reminder` (`scheduled.py:55`, "datetime - NoneType") on cases where `triage_at` is null. Commit `32fa810f` guarded `stable_at` for the stable reminder but left `triage_at` unguarded in the close reminder. That error predates the refactor (it appears from 07-28), so it is not what stopped the Monday sends. It is still a separate bug that skips some triage cases, and the fix should cover it too.

I have not changed any code. The likely fix is to compare against `date.today().weekday() == calendar.MONDAY` (0-based, which matches `calendar.MONDAY`), or `isoweekday() == 1`. Adding a guard for `triage_at` in the close reminder would be the matching change. I can make these edits and add a test for the Monday check if you want.

----- next turn -----

The Monday reminder check is fixed, and a regression test now covers it. Nothing is committed.

**Fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use 0-based numbering. The refactor compared the 1-based `isoweekday()` with `calendar.MONDAY`, which is 0, so the check never passed.

**Also changed:** the triage close reminder had the same unguarded arithmetic that `32fa810f` fixed for stable cases. It raised on every run for cases with a null `triage_at`. I wrapped it in the same `if case.triage_at:` guard. This goes slightly beyond the weekday bug, so drop that hunk if you'd rather handle it separately.

**Regression test** (`tests/case/test_case_scheduled.py`): it pins the date to each day of one week and asserts that only Monday returns True.
- Against the original code, the Monday case fails.
- With the fix, all 7 cases pass.

**Wider run:** `python -m pytest tests/case tests/case_cost` gives 41 passed, using the local PostgreSQL.

The test only covers the weekday helper, not the full scheduled job. Running the job end to end would need the org-schema task machinery, so I didn't build that.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, so those cases get their Monday reminder. Nothing is committed.

**Cause of the TypeError:** the job does `datetime.utcnow() - case.triage_at`, and some cases in Triage have a null `triage_at`. `triage_at` is only stamped in `case_triage_status_flow`, which runs on the normal transitions. The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly and skips that flow, so a case reopened this way never gets a `triage_at`. This is the most likely source. I can't confirm it from the logs, because they don't record case IDs, and I don't have production data. The check would be a query for Triage cases with a null `triage_at`, and whether they were reopened.

**Changes:**
- `src/dispatch/case/scheduled.py`: `triage_start = case.triage_at or case.created_at`. The earlier `if case.triage_at:` guard is gone, so these cases are now counted rather than skipped.
- `tests/case/test_case_scheduled.py`: three tests that run the real job body against the test database, with the send mocked and the date pinned to a Monday:
  - a case with no `triage_at` and created 8 days ago gets the reminder;
  - a case with no `triage_at` and created 2 days ago does not;
  - when `triage_at` is set, it is used rather than `created_at`.

  The first test fails if the fallback is removed. All 10 scheduled-tests pass, and `python -m pytest tests/case tests/case_cost` gives 44 passed.

**Not changed:**
- The reopen button still skips the triage flow. I left it alone because you asked for the fallback, but it is the path that produces these cases.
- The stable reminder still skips cases with a null `stable_at` (`if case.stable_at:`). It doesn't raise, but those cases get no weekly reminder. I can apply the same `created_at` fallback there if you want it.

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving. No reminder settings changed.
- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (1 for Monday) with `calendar.MONDAY` (0). The check was never true, so both weekly reminders were suppressed. Before commit `c509d45e` (a refactor that moved the check into this helper), the code used `isoweekday() == 1`, which was correct.
- **Deploy:** image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC. Commit `81d8ae42` contains `c509d45e`. The last Monday reminders were sent on 2025-08-11, under the earlier image. No reminders were sent on 2025-08-18 or later in the logs.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the original code and passes with the fix.
- **Secondary error:** `case_close_reminder` raised a `TypeError` every evening because some Triage cases have a null `triage_at`. The job now counts from `created_at` when `triage_at` is missing. Tests cover the fallback and the preference for `triage_at`.
- **Likely source of null `triage_at`:** the Slack reopen button sets Triage directly and skips the flow that stamps `triage_at`. This is inferred from the code; the logs don't record case IDs, so it is unconfirmed.
- **Open items:** the reopen path is unchanged. The stable reminder still skips cases with a null `stable_at` rather than using the `created_at` fallback.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at