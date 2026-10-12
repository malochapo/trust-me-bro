**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") added a helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` in Python (weeks start at Monday = 0), but `isoweekday()` returns `1` for Monday (1–7). The comparison is therefore always false, so the helper never returns true. The original code compared against `1`, which was correct. The refactor silently changed the constant, so both weekly paths stopped:

- `case_close_reminder` (triage, line ~49) uses `q >= 1 and _is_reminder_day()`.
- `case_stable_reminder` (stable, line ~95) uses the same check.

The daily triage reminder, `case_triage_reminder`, doesn't call the helper, which is why it still arrives. Nobody changed settings, which matches the symptom.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on 2025-08-13 at 16:40Z (scheduler pod `scheduler-mhtsgqwwx-q5q2n` and web pod `web-5dkmr9s9s-xxktx`). I confirmed with `git merge-base --is-ancestor` that `c509d45e` is contained in `81d8ae42`. The commit landed 2025-08-12 21:05Z, and the deploy image is the one after it on main.

**Evidence from the logs:**
- Monday 2025-08-04: 6 "Case close reminder sent" lines. Monday 2025-08-11 (before the commit): 5 sent.
- Monday 2025-08-18 (after the deploy): 0 sent. Triage reminders continue daily through 2025-08-20.
- The scheduler ran on 2025-08-11 at 18:00Z, before the commit, so its reminders are expected.

**Not the cause:** `32fa810f` ("not all cases have a stable_at date") is in the same image. It fixed a `NoneType` error that appeared in the logs every day from 2025-07-28 in `case_stable_reminder`. That fix shouldn't stop reminders, and the errors are the expected pre-fix behaviour.

**Suggested fix (not applied, per your instruction):** use the value that matches `isoweekday()`, e.g. `date.today().isoweekday() == 1`, or switch the helper to `date.today().weekday() == calendar.MONDAY`. The second is the one that keeps `calendar.MONDAY`. A test that pins the helper's result for a known Monday would have caught this.

I made no code changes. The "daily" reminder discrepancy was the only thing you described that I didn't check against the logs directly, but the triage counts above confirm it.

----- next turn -----

The weekly reminders are fixed, and a regression test covers the bug.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, matching `calendar.MONDAY`. The previous `isoweekday()` counts Monday as 1, so the comparison never matched. Both `case_close_reminder` (triage) and `case_stable_reminder` (stable) go through this helper, so both are fixed. The incident weekly check at `incident/scheduled.py:229` already compares `isoweekday() == 1` correctly, so I left it alone.

**The regression test** (`tests/case/test_case_scheduled.py`): it patches the module's `date` to fix "today" and checks that Monday 2025-08-18 returns true, while Tuesday and Sunday return false. The Monday case fails on the original line and passes on the fix. I checked both.

**Verification:**
- `python -m pytest tests/case/test_case_scheduled.py`: 3 passed.
- `python -m pytest tests/case`: 18 passed, against the local PostgreSQL.

I did not commit or push. The changes are in the working tree: one edited line in `scheduled.py` and the new test file.

I wrote the test against the helper rather than the full scheduled functions. Those are wrapped in a project-context decorator that opens its own session, so a Monday integration test would need more setup. If you want the end-to-end path covered too, I can add that next.

----- next turn -----

The evening `TypeError` is fixed, and cases without a `triage_at` now get their weekly reminder counted from creation.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at = None`. The only place that sets it is `case_triage_status_flow` (`case/flows.py:594`), which runs on transitions through the flow. Three Slack handlers assign `case.status = CaseStatus.triage` directly and skip the flow: `plugins/dispatch_slack/case/interactive.py` at lines 1312, 1427, and 2246. Cases moved to triage that way never get a timestamp. The job's `try` catches the error, logs it, and skips the case, so it fails every evening at 18:00.

**Fix** (`src/dispatch/case/scheduled.py:47`): `span = datetime.utcnow() - (case.triage_at or case.created_at)`, with a one-line comment explaining the fallback.

**Tests** (`tests/case/test_case_scheduled.py`): two new cases run the real job on a Monday for a triage case with `triage_at = None`. One is 8 days old and should get a reminder. The other is 2 days old and should not. I reached the job through the scheduler's registered tasks, since the decorator returns `None` at module level. With the fallback reverted, the 8-day test fails with the same `TypeError` from the logs. With the fix, all five tests in the file pass, and `python -m pytest tests/case` passes 20 of 20.

**Not changed:** the Slack handlers still bypass the transition flow, so those cases still have no `triage_at`. Also, `case_triage_reminder` and the other reminder paths are untouched. Setting `triage_at` in those three handlers would be the proper follow-up. I left it out because you asked for the fallback. Tell me if you want it.

----- next turn -----

**Recap**

- **Weekly reminders stopped after the 2025-08-13 deploy.** Commit `c509d45e` moved the Monday check into `_is_reminder_day()`, which compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison never matched, so the weekly triage and stable reminders stopped. Daily triage reminders don't use the check and kept arriving. The logs show 5 close reminders on Monday 2025-08-11, before the commit, and none on Monday 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the old line and passes on the fix.
- **Evening TypeError:** `case_close_reminder` subtracted from `case.triage_at`, which is `None` for cases that were moved to triage through three Slack handlers that set the status directly and skip the transition flow. The error was caught and the case skipped, so those cases never got a reminder. **Fix:** the job now counts from `case.triage_at or case.created_at`. Two new tests run the real job on a Monday. One checks that an 8-day-old case gets a reminder, and the other that a 2-day-old case does not. The 8-day test fails without the fallback, with the same `TypeError`.
- **Verification:** `python -m pytest tests/case` passes 20 of 20 against the local PostgreSQL.
- **Status:** both fixes are uncommitted in the working tree, and nothing has been deployed. The Slack handlers that skip `triage_at` are still open. Setting it there would be the proper follow-up.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at