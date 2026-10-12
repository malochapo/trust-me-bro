**Root cause:** `_is_reminder_day()` compares against the wrong weekday number, so the weekly close and stable reminders never fire. The daily triage reminder doesn't call that helper, so it still works.

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (Python's `weekday()` convention), but `isoweekday()` returns `1` for Monday. The check is never true, so `case_close_reminder` and `case_stable_reminder` never send. I confirmed both values in Python.

**The deploy:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12 14:05 PT). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, and that is where the `0`/`1` mismatch was introduced. The first rollout containing it was image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler and web pods at 2025-08-13 16:40 UTC. `c509d45e` is an ancestor of `81d8ae42`, and it is not in the previous image `main-b05613b5`.

**Log evidence:**
- Close and stable reminders went out on Monday 2025-08-04 and Monday 2025-08-11, both before the commit.
- No close or stable reminders were sent on Monday 2025-08-18, the first Monday after the rollout. The logs end 2025-08-20.
- Triage reminders kept firing daily (33 sends through 08-20), as you described.

**Not the cause:** the scheduler logs show `case_stable_reminder` and `case_close_reminder` raising `unsupported operand type(s) ... NoneType` from 07-28 onward. Those came from cases with a null `stable_at` or `triage_at`. They were caught by the per-case `try`/`except`, so they only logged. Commit `32fa810f` (2025-08-11) fixed the `stable_at` case. That fix predates the rollout, and the 08-11 Monday sends still went out, so it doesn't explain the mid-August gap.

No code has been changed. A fix would compare `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. I'd add a test that pins the reminder day to a known Monday, since nothing currently exercises this helper.

----- next turn -----

The weekly close and stable reminders now fire on Mondays again. The fix is one line, and the new regression test fails on the old code and passes with the fix.

**The fix** (`src/dispatch/case/scheduled.py:33`): `isoweekday()` returns 1 to 7, with Monday as 1, but `calendar.MONDAY` is 0. I changed the call to `date.today().weekday()`, which uses the same 0-based numbering as `calendar.MONDAY`.

**The test** (`tests/case/test_case_scheduled.py`, new file): it patches `date` in the scheduler module to a fixed day, then checks `_is_reminder_day()` for Monday through Sunday of 2025-08-18 to 08-24. Monday must return `True` and the other six days `False`.
- Without the fix, the Monday case fails and the other six pass.
- With the fix, all seven pass.

I patched `date` rather than adding a time-freezing dependency, so no new packages were needed.

**Test runs:** `python -m pytest tests/case tests/case_cost` gives 41 passed, against the local PostgreSQL. I did not run the full suite. `ruff` isn't installed in this environment, so I couldn't lint.

I haven't committed anything. The changes are in the working tree: the one-line edit and the new test file.

----- next turn -----

The evening `TypeError` is `case.triage_at` being `None` when the job subtracts it from the current time. The job now falls back to `created_at`, so those cases get their weekly reminder. Tests cover the fallback, and I ran them against the local PostgreSQL.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at` for every case in triage. `triage_at` is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`, so any case that reaches triage without going through that flow has a null value. The per-case `try`/`except` catches the error and logs it, which is why it shows up as a `TypeError` every evening and why the other cases still send.

Two code paths set the status to triage directly and skip that flow:
- `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`, the reopen button. It sets `case.status = CaseStatus.triage` directly.
- `src/dispatch/plugins/dispatch_slack/case/interactive.py:1312`, the new-to-triage button. It calls the transition dispatcher first, so it is probably fine.

The logs don't include case IDs, so I can't confirm which case path produced the null values in production. I haven't changed those paths.

**Fix** (`src/dispatch/case/scheduled.py:47-50`): the job now counts from `case.triage_at or case.created_at`. The rest of the logic is unchanged.

**Tests** (`tests/case/test_case_scheduled.py`, three new cases):
- A case with no `triage_at`, created 8 days ago, gets a reminder on a reminder day.
- A case with no `triage_at`, created 2 days ago, does not.
- A case with `triage_at` set uses it even when `created_at` is recent.

The tests call the undecorated job through the scheduler's registered-task list. I confirmed that with the fallback removed, the first test fails with the same `TypeError` as the logs. With the fix restored, all 10 tests in the file pass. `python -m pytest tests/case tests/case_cost` gives 44 passed.

**Not changed:** `case_stable_reminder` has the same kind of gap, but it skips cases with a null `stable_at` instead of falling back. That is why stable cases without `stable_at` never get the reminder. You asked only about the close job, so I left it alone. Say if you want the same fallback there.

Nothing is committed. The changes are in the working tree: the edit to `scheduled.py` and the new test file.

----- next turn -----

## Recap

**Weekly reminder bug.** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check was never true, so the weekly close and stable reminders never sent. Triage reminders don't use this helper, so they kept firing daily. Commit `c509d45e` introduced the mismatch when it moved the check into the helper. It reached production in image `main-81d8ae42`, rolled out on 2025-08-13. The logs show close and stable reminders on Monday 2025-08-11, before the rollout, and none on Monday 2025-08-18.

**Fix.** The helper now uses `date.today().weekday()`, which matches `calendar.MONDAY`. `tests/case/test_case_scheduled.py` checks Monday through Sunday. It fails on the old code for Monday and passes with the fix.

**Evening `TypeError`.** `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached triage through other paths had it null. The per-case `try`/`except` logged the error and moved on, so the other cases still got reminders. The job now counts from `created_at` when `triage_at` is missing. Three tests cover the fallback; removing it reproduces the logged `TypeError`. The case and case_cost suites pass (44 tests).

**Open items.**
- The logs don't name the affected cases, so I haven't confirmed which path produced the null `triage_at` values. The reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py` sets triage directly and is a likely candidate.
- `case_stable_reminder` still skips cases with a null `stable_at` rather than falling back. That's a separate gap, which I haven't changed.
- Nothing is committed yet.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```