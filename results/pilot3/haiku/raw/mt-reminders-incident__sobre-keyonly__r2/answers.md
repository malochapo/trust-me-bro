**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the Monday check with a helper that compares against the wrong constant.

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` in Python (weeks start Monday = 0), but `isoweekday()` returns `1` for Monday. The condition is never true, so `case_close_reminder` and `case_stable_reminder` never send the weekly reminder. The original code was `date.today().isoweekday() == 1`, which was correct. The daily `case_triage_reminder` doesn't call this helper, which is why the triage reminders still arrive.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update", #6183). It started on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` and the web pod at **2025-08-13 16:40:06Z**, replacing `main-b05613b5`. `c509d45e` is an ancestor of `81d8ae42`, and `b05613b5` predates `c509d45e`.

**Log evidence:**
- Monday 2025-08-04 and Monday 2025-08-11 both sent `Case close reminder sent to …` lines, all from the old pod `scheduler-xdp7k6gs2q-w6cj7`. The 08-11 sends happened before the refactor was deployed.
- No close reminders were sent on Monday 2025-08-18, the first Monday on the new image. Triage reminders still went out that day (`Case triage reminder sent to l.nguyen@…`).

**Other things I noticed (not the cause, not changed):**
- `case_close_reminder` has logged `NoneType` errors at line 47 (`datetime.utcnow() - case.triage_at`) every day since 2025-08-05. The per-case `try/except` swallows them, so other cases still get processed, but cases with no `triage_at` are skipped silently. This is a separate gap and worth fixing the same way as `stable_at` in `32fa810f`.
- `case_stable_reminder` had the same `stable_at` crash until `32fa810f` (08-11) added the guard. That fix is in the 08-13 deploy too.

**Suggested fix (not applied):** change the helper to `date.today().isoweekday() == 1`, or `calendar.MONDAY + 1` if you prefer the named constant. Add a test that pins a known Monday, since the existing tests presumably didn't cover this path. I also didn't check whether the `incident/scheduled.py:229` weekly check has a similar issue; it uses a literal `== 1`, so it looks correct.

----- next turn -----

I fixed the weekday check and added a regression test. The case tests pass (22 passed), and the new test fails when the bug is put back.

**The fix** (`src/dispatch/case/scheduled.py:33`): `calendar.MONDAY` is 0-based, so the comparison now uses `date.today().weekday()`, which is also 0-based. The original `isoweekday() == 1` was also correct; I chose `weekday()` so the comparison uses the same numbering as the constant.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it pins `date.today()` to each day of the week in turn and asserts that `_is_reminder_day()` is true only on Monday. With the buggy comparison, the Monday case fails (1 failed, 6 passed), and with the fix all 7 pass.

Limits of the test:
- It covers the helper, not the two scheduled tasks end to end. Calling `case_close_reminder` or `case_stable_reminder` in a test would have to go through the project-context decorator, which opens its own DB session, so I left that out.
- It patches the module's `date` name because the repo has no time-freezing library.

I haven't committed anything. The working tree has the one-line change and the new test file.

----- next turn -----

The close-reminder job now falls back to `created_at` when `triage_at` is missing, with tests. The case directory passes (25 tests), and the fallback test fails when the fix is reverted.

**What causes the error:** the job subtracts `triage_at` from `utcnow()`, and that field is NULL for some triage cases. Python raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` logs it, so the other cases still run.

The NULL comes from the reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py`, `reopen_button_click`. It sets `case.status = CaseStatus.triage` directly and never calls the triage transition flow, which is the only place `triage_at` is set (`src/dispatch/case/flows.py:594`). A closed case reopened this way keeps NULL `triage_at`, and a case that was never triaged has no timestamp at all. The log errors start 2025-07-28 and never stop, so that is the path the logs point to. I didn't confirm which cases hit it in production.

**The change** (`src/dispatch/case/scheduled.py:47-50`): `triage_started_at = case.triage_at or case.created_at`, so these cases count from creation and get their weekly reminder.

**Tests** (`tests/case/test_case_scheduled.py`):
- A triage case with no `triage_at` created 14 days ago gets the reminder. This is the regression test; it fails on the old code.
- A recent case with no `triage_at` does not get one.
- A case with `triage_at` set still counts from `triage_at`.

The job is reached through the scheduler's registered task list, because the decorators open their own per-organization sessions. Those helpers are in the test file. The factory's status default overrode the status passed in, so the tests set triage status after creating the case, as `test_case_messaging.py` does.

**Things I did not change:**
- The reopen handler still skips the transition flow. Setting `triage_at` there would be the root-cause fix; I left it because you asked for the fallback.
- `CaseBase.created_at` defaults to a timezone-aware `datetime.now(timezone.utc)` (`src/dispatch/models.py:40`), while the job compares against naive `utcnow()`. The scheduler loads cases from the database, so this works today, but a case object created in memory and passed to this job would raise the same `TypeError`.
- `case_stable_reminder` still skips cases with no `stable_at` without logging. You didn't ask about it, so I left it alone.

Nothing is committed. The changes are in `src/dispatch/case/scheduled.py` and the new test file.

----- next turn -----

Recap of the Monday reminder incident and the fixes. Nothing is committed.

**What happened:** Weekly reminders for long-running triage and stable cases stopped after the 2025-08-11 Monday run. The daily triage reminders kept going.

**Weekday bug:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced it in a refactor that moved the check into the helper. The fix uses `date.today().weekday()`, which matches `calendar.MONDAY`. A regression test pins each weekday and fails with the bug reinstated.

**Deploy:** image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC, replacing `main-b05613b5`. No close reminders went out on the next Monday, 2025-08-18.

**Evening TypeError:** `case_close_reminder` subtracted `triage_at` from the current time, and `triage_at` is NULL for some triage cases. The reopen button handler (`reopen_button_click`, `src/dispatch/plugins/dispatch_slack/case/interactive.py`) sets triage status directly without the transition flow, which is the only code that sets `triage_at`. The job now uses `created_at` when `triage_at` is missing, with tests covering that case, a recent case, and the normal case.

**Not fixed, for follow-up:**
- The reopen handler should set `triage_at` through the transition flow. I added the fallback instead, as requested.
- `created_at` defaults to a timezone-aware datetime while the job compares against naive `utcnow()`. This works for cases loaded from the database but would raise `TypeError` for in-memory cases.
- `case_stable_reminder` still silently skips stable cases with no `stable_at`.

**Report fields:**

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at