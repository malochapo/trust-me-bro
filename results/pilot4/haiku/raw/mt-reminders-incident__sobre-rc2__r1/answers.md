**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday gate for the long-running reminders. It replaced the inline check `date.today().isoweekday() == 1` with a new helper that compares against `calendar.MONDAY`:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, because Python's `calendar` uses `weekday()` numbering (Monday=0). `isoweekday()` uses 1 for Monday, so the condition is `isoweekday() == 0`, which is never true. Both `case_close_reminder` (triage) and `case_stable_reminder` (stable) call `_is_reminder_day()`, so both weekly reminders stopped. The daily triage reminders are not gated by this helper, which is why they still arrive.

**Evidence from the logs:**
- The last weekly long-running reminders were sent on Monday 2025-08-11 at 18:00 UTC (for example, `Case close reminder sent to r.patel@…`, plus several others).
- On Monday 2025-08-18 there are no "Case close reminder" lines. Only daily triage reminders and an incident reminder appear, and that pattern continues through 2025-08-20.
- Earlier Mondays, such as 2025-08-04, show the same close-reminder pattern as 08-11, so the check was working before the change.

**The deploy that shipped it:** the commit is an ancestor of `main-81d8ae42`, and that image is the one both pods started on:
- `scheduler.log:18851` — `2025-08-13T16:40:06Z` scheduler pod `scheduler-mhtsgqwwx-q5q2n` started on `registry.example.com/dispatch:main-81d8ae42`.
- `api.log:13201` — `2025-08-13T16:40:07Z` web pod started on the same image.

The previous image, `main-b05613b5` (started 2025-07-30), does not contain `c509d45e`. The 2025-08-11 sends came from that older image and were correct.

**Side note, not the cause:** `case_stable_reminder` logged `unsupported operand type(s) … 'NoneType'` at `scheduled.py:93` every day from 2025-07-28 onward. The `if case.stable_at:` guard that fixes this is in `32fa810f`. I did not check whether that guard was live in production during the window, so it's worth a separate look, but it does not explain the Monday gap.

I have not changed any code. The fix is to compare against Python's `weekday()` or use `1` for Monday: `date.today().weekday() == calendar.MONDAY`. It would also be worth adding a test that pins `_is_reminder_day()` to a Monday date.

----- next turn -----

The fix is in, and the regression test is in place. I did not commit anything.

**Fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both sides use Python's Monday=0 numbering. The old `isoweekday()` returns 1 for Monday, so it never matched `calendar.MONDAY` (0).

**Regression test** (`tests/case/test_case_scheduled.py`): a parametrized test that pins `date.today()` and asserts `_is_reminder_day()` is True on Monday 2025-08-18 and False on Sunday, Tuesday, and Saturday.

**Verification:**
- With the fix reverted, the Monday case fails (`1 failed, 3 passed`). With the fix in place, all 4 pass.
- `python -m pytest tests/case` passes: 19 tests.
- I did not run the full suite.

The test checks the gate itself, not the full reminder path, so it does not need database fixtures for this change. It would have failed in the refactor commit's CI.

----- next turn -----

The close reminder no longer throws. Cases with no `triage_at` now count from `created_at`, and a regression test covers it. Nothing is committed.

**Cause:** `triage_at` is only set by `case_triage_status_flow`. The Slack reopen button (`src/dispatch/plugins/dispatch_slack/case/interactive.py`, `reopen_button_click`) sets `case.status = CaseStatus.triage` directly and never runs that flow. A case reopened without ever having been triaged therefore sits in Triage with `triage_at = NULL`, and `datetime.utcnow() - None` raises the `TypeError`. The logs show 16 of these from 2025-07-28 onward.

I did not confirm this against the database. The logs don't include case IDs, so I can't tell which cases hit the bug. The query to check is `SELECT id FROM "case" WHERE status = 'Triage' AND triage_at IS NULL;` against production.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`):
```python
triage_started = case.triage_at or case.created_at
span = datetime.utcnow() - triage_started
```
Cases with a `triage_at` keep counting from it.

**Test** (`tests/case/test_case_scheduled.py`): `test_case_close_reminder_falls_back_to_created_at` creates two Triage cases, one with no `triage_at` and one with a recent one. Both have a `created_at` 14 days ago. It runs the job on a forced Monday and checks that only the untimed case gets a reminder. The test looks the job up in `scheduler.registered_tasks`, since the decorators don't return the function.
- With the fallback removed, the test fails with the same `TypeError`.
- With the fallback in place, `python -m pytest tests/case` passes (20 tests).

**Choices I made:**
- I left `case_stable_reminder` alone. It skips cases with no `stable_at` rather than falling back, and you asked only about the close reminder.
- The reopen button still bypasses the triage flow. I didn't change that, since the fallback covers the symptom and the fix is in the reminder code.

----- next turn -----

Recap:

- **Weekday bug:** commit `c509d45e` (Jordan Lee, 2025-08-12) moved the Monday check into `_is_reminder_day()` and compared `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so the weekly long-running reminders for triage and stable cases stopped. Daily triage reminders were unaffected.
- **Deploy:** `main-81d8ae42` started on both the API and scheduler pods on 2025-08-13 at 16:40 UTC. It is the first image that contains `c509d45e`. The previous image, `main-b05613b5`, does not.
- **Last good Monday:** 2025-08-11 at 18:00 UTC sent weekly close reminders. The first missed one was Monday 2025-08-18.
- **Evening TypeError:** `case_close_reminder` failed on cases in Triage with no `triage_at`. The likely path is the Slack reopen button, which sets Triage without running the triage flow. I have not confirmed this against production data.
- **Fixes (uncommitted):** `_is_reminder_day()` now uses `weekday()`, and the close reminder falls back to `created_at`. Both have regression tests. `python -m pytest tests/case` passes (20 tests). These changes are not deployed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at