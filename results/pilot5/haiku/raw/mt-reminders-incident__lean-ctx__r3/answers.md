The root cause is a bug in the weekly-reminder day check, introduced by commit `c509d45e` and shipped to production in deploy `main-81d8ae42` on 2025-08-13. I haven't changed any code.

**Root cause**

`_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares two different numbering schemes:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

- `date.isoweekday()` returns 1 for Monday (Monday through Sunday are 1 through 7).
- `calendar.MONDAY` is 0 in the standard library (Monday is 0 in `calendar`).

So the check is never true, and the weekly reminders are never sent. Both `case_close_reminder` (line 49, long-running triage cases) and `case_stable_reminder` (line 95, stable cases) call this helper, which is why both stopped. The daily `case_triage_reminder` doesn't use it, which matches what you're seeing.

I could not run a Python check of `calendar.MONDAY` in this session because the shell blocked inline interpreter calls. The value 0 is documented stdlib behavior, so I'm confident in it, but it's the one claim I didn't execute.

**Commit and deploy**

- Commit: `c509d45e` "refactor(case): share the weekly reminder check" by Jordan Lee, 2025-08-12 14:05 PT. It replaced the working inline `date.today().isoweekday() == 1` with `_is_reminder_day()`. The refactor's behavior change is exactly this constant swap.
- Deploy: `81d8ae42` "fix(case): exclude resolved_by in update (#6183)" by David Whittaker, 2025-08-12 14:47 PT. `c509d45e` is an ancestor of it and of HEAD. The scheduler container restarted on image `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40:06Z (`scheduler.log:18851`). The API pod got the same image at 16:40:07Z (`api.log:13201`).

**Log evidence**

- "Case close reminder sent" (Monday sends from the weekly path): 4 on 07-28, 6 on 08-04, 5 on 08-11, and none on 08-18 or after. That matches the window before and after the 08-13 deploy.
- The previous scheduler deploy, `main-b05613b5`, was on 07-30 and predates the refactor, so the Monday runs on 08-04 and 08-11 used the old working check.

**Side note, not the cause**

Before the 08-13 deploy, the stable reminder logged a `datetime - NoneType` error daily for cases with no `stable_at`, and the triage close path had the same error for `triage_at`. Commit `32fa810f` ("fix(scheduler): not all cases have a stable_at date") was in the same deploy, and the errors stop after 08-12. This is separate from the Monday bug and doesn't explain the missing reminders.

**Suggested fix (not applied)**

Change line 33 to `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based and matches `calendar`. Add a test that pins a known Monday, since the 0-versus-1 mismatch is easy to miss in review.

----- next turn -----

The fix is in and the regression test is added. Nothing is committed yet.

**Fix:** `src/dispatch/case/scheduled.py:33` now reads `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar`, so Monday matches. The old `isoweekday()` is 1-based, so it never matched.

**Regression test:** `tests/case/test_case_scheduled.py` is new. It pins `_is_reminder_day()` to a Monday (2025-08-18), which must return True, and to each of the other six days, which must return False.

**Verification:**
- With the fix, `python -m pytest tests/case -q` gives 22 passed, including the 7 new cases.
- With the old line put back temporarily, the Monday case fails with `assert False is True`. The other six pass. So the test would have caught this bug.
- I restored the fix afterwards. `git status` shows only the one-line change in `scheduled.py` and the new test file.

I didn't add a test that calls `case_close_reminder` or `case_stable_reminder` end to end. The helper test covers the broken line directly, and the scheduled functions need the project-task decorator context. Tell me if you want an end-to-end test as well.

----- next turn -----

The close reminder's nightly TypeError comes from cases in `triage` with no `triage_at`. The job now counts those from `created_at`, and there's a regression test for it.

**Cause**

`case_close_reminder` subtracts `case.triage_at` with no guard. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:595`), which runs only on transitions into triage. Two paths skip it:

- **Creating a case with `status=triage`:** `service.create` (`src/dispatch/case/service.py:205`) sets the status directly and never runs the transition flow.
- **Clearing the field:** `CaseUpdate` exposes `triage_at`, and `service.update` sets whatever fields the request includes.

I inferred this from the code. The logs don't record case IDs, so I haven't confirmed which path produced the nightly failures in production.

**Correction to my earlier report:** I said the close-reminder errors stopped after 08-12. That was wrong. I had only matched the old line number (`:51`). After the 08-13 deploy the same TypeError is logged once every evening at `scheduled.py:55`, through 08-20.

**Fix** (`src/dispatch/case/scheduled.py:47-49`)

```python
# cases created directly in triage never get a triage_at, so count from creation
triage_started_at = case.triage_at or case.created_at
span = datetime.utcnow() - triage_started_at
```

**Test** (`tests/case/test_case_scheduled.py`)

- `test_case_close_reminder_counts_from_created_at_without_triage_at`: a triage case with no `triage_at`, created 8 days ago, gets the reminder.
- `test_case_close_reminder_uses_triage_at_when_set`: a case with a recent `triage_at` but an old `created_at` gets no reminder, so the fallback doesn't override a real timestamp.

The scheduler decorator doesn't return the task, so the test finds it in `scheduler.registered_tasks` and unwraps it. I also stubbed `_is_reminder_day` to True so the test doesn't depend on the day it runs.

**Verification**

- `python -m pytest tests/case -q`: 24 passed.
- With the fallback removed temporarily, the first test fails, so it catches the bug. I restored the fix afterwards.

**Not changed**

- The stable reminder still skips cases with no `stable_at` (from `32fa810f`). Those cases never get a stable reminder. I left it alone because you asked about the close job. Say if you want the same `created_at` fallback there.
- Nothing is committed.

----- next turn -----

## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** Assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.

- **Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check was never true, so no weekly reminders were sent. The fix is `date.today().weekday() == calendar.MONDAY`.
- **How it shipped:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) introduced the mismatch. It reached production in deploy `main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update"), which the scheduler started at 2025-08-13T16:40Z. The previous deploy, `main-b05613b5`, predates the refactor.
- **Evidence:** "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6) and 08-11 (5). There are none on 08-18 or later, through the end of the logs on 08-20.
- **Evening TypeError:** `case_close_reminder` subtracts `case.triage_at` with no guard, and that field is NULL for some cases in triage. Cases can reach triage without `triage_at` when they are created directly in that status, because `service.create` skips the triage transition flow. The job now counts those cases from `created_at`. The error was logged nightly through 08-20 and was not limited to 08-12, which I had wrongly reported earlier.
- **Other errors:** The stable reminder's `stable_at` TypeError stopped after 08-12, when `32fa810f` shipped. It is not part of this incident.

**Current state:** The working tree has the weekday fix, the `created_at` fallback, and new tests in `tests/case/test_case_scheduled.py`. Those tests fail on the old code. `python -m pytest tests/case -q` passes 24 tests. Nothing is committed. The stable-case path still skips cases with no `stable_at`, which you may want to decide on separately.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at