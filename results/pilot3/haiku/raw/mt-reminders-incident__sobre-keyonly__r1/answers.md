## Root cause

The weekly reminders are broken by a weekday comparison that can never be true. Commit `c509d45e` (“refactor(case): share the weekly reminder check”, Jordan Lee, 2025-08-12) moved the Monday check into a helper in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`date.today().isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's `calendar` numbers weeks from Monday = 0). So `_is_reminder_day()` returns False every day. The old inline check was `date.today().isoweekday() == 1`, which was correct. Both weekly paths call the helper: `case_close_reminder` (triage, line 49) and `case_stable_reminder` (line 95). That's why both stopped. The daily `case_triage_reminder` doesn't use the helper, so it still sends.

I verified this in Python: `calendar.MONDAY = 0`, `isoweekday()` for 2025-08-18 (a Monday) is 1.

## The deploy

- `c509d45e` is an ancestor of `81d8ae42` (`fix(case): exclude resolved_by in update (#6183)`).
- The scheduler and web containers rolled out `registry.example.com/dispatch:main-81d8ae42` on **2025-08-13 at 16:40Z**, replacing `main-b05613b5`.
- Logs agree with the timing. The last Monday close reminders went out on 08-11 (under the old image). After the deploy, zero "Case close reminder sent" lines appear, including on Monday 08-18. Daily triage reminders continue.

## Related, not the cause

- Before this, `case_stable_reminder` failed every day from 07-28 with `datetime - NoneType` on `case.stable_at`. Commit `32fa810f` (08-11) added the `if case.stable_at:` guard, which is in the repo now. The guard shipped in the same 08-13 image, so the stable path was fixed at the same time the weekday check broke it.
- `case_close_reminder` also fails for some cases with `triage_at = None` (line 47 in the 08-18 log). That error is caught per case, so it doesn't stop the job, but those cases are skipped. Worth a separate ticket.

## Suggested fix (not applied)

Use the 0-based weekday to match `calendar.MONDAY`:

```python
return date.today().weekday() == calendar.MONDAY
```

Alternatively, `date.today().isoweekday() == 1` restores the pre-refactor behavior. A unit test that freezes the date to a Monday would have caught this.

I haven't changed any code. I only read the logs and the git history.

----- next turn -----

The weekly reminders are fixed, and there's a regression test for the Monday check. Nothing is committed.

**The fix** is in `src/dispatch/case/scheduled.py:33`. `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are zero-based, so Monday matches. The previous `isoweekday()` is one-based, which made the comparison never true.

**The regression test** is `tests/case/test_case_scheduled.py`. It patches the module's `date` so the test controls "today", and checks that Monday returns True while Tuesday and Sunday return False. I ran it against the old line and it failed on Monday; with the fix it passes.

**Test results**
- `python -m pytest tests/case/test_case_scheduled.py`: 3 passed.
- `python -m pytest tests/case`: 18 passed.
- I did not run the full suite.

Choices I made:
- I patched `date` rather than adding `freezegun`, since it isn't a project dependency.
- The test covers only the helper, not the full stable and triage jobs, because those are wrapped in the project-context decorator and would need more setup. The helper is the part that broke.

Still open from the investigation: `case_close_reminder` fails on cases where `triage_at` is null. The error is caught per case, so the job continues, but those cases never get the reminder. It's a separate fix.

----- next turn -----

The triage close reminder now counts from `created_at` when a case has no `triage_at`, and it has regression tests. I haven't committed anything.

**Cause:** `triage_at` is only set by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Several paths put a case into `triage` without running that flow, so the timestamp stays null:
- `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py` sets `case.status = CaseStatus.triage` and never calls the flow.
- `triage_button_click` in the same file sets the status directly on one branch, skipping the flow.
- `case_status_transition_flow_dispatcher` has an `(_, CaseStatus.triage)` branch that logs "Unexpected previous state" and returns without setting `triage_at`. Cases coming from stable or escalated take this branch.

Then `datetime.utcnow() - case.triage_at` raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try` catches it, so the job finishes but skips those cases. The logs have 24 of these errors. They don't include case IDs, and I have no database access, so I couldn't match the 24 errors to a specific path. I didn't change those paths; the fallback covers the symptom, and the root cause in the flow is a separate fix.

**Fix** (`src/dispatch/case/scheduled.py:47-50`):
```python
# not every triage case has a triage_at, fall back to when the case was created
started_at = case.triage_at or case.created_at
span = datetime.utcnow() - started_at
```

**Tests** (`tests/case/test_case_scheduled.py`):
- A triage case with no `triage_at`, created 17 days before the Monday, gets the reminder.
- A case with no `triage_at`, created 3 days before, does not.

The job is run via the scheduler's registered task, with the decorators unwrapped. I also froze `utcnow` as well as `date`, because the first draft compared against the real clock and passed for the wrong reason.

**Results**
- `python -m pytest tests/case/test_case_scheduled.py`: 5 passed.
- With the fallback removed, the "counts from created_at" test fails.
- `python -m pytest tests/case`: 20 passed.

One caveat: `created_at` defaults to a timezone-aware value in Python, but the column is naive. Rows loaded from the database are naive, so the job is fine. An unsaved in-memory case would raise a `TypeError` on the subtraction.

----- next turn -----

## Recap

**Symptom:** Since mid-August, assignees no longer receive the Monday reminders for long-running triage and stable cases. The daily triage reminders still arrive, and nobody changed the settings.

**Root cause (weekday bug):** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`. `isoweekday()` is one-based (Monday = 1), while `calendar.MONDAY` is zero-based (Monday = 0). The helper therefore returned False every day, so no weekly reminder was sent. Both the triage close reminder and the stable close reminder call the helper, which is why both stopped. The daily triage reminder doesn't call it, so it kept working.

**Deploy:** Commit `c509d45e` is an ancestor of `81d8ae42`. The scheduler and web containers rolled out `main-81d8ae42` on 2025-08-13 at 16:40Z. On 2025-08-11, the last Monday before the deploy, close reminders were still sent. After the deploy, none were sent.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. The regression test `tests/case/test_case_scheduled.py::test_is_reminder_day` fails on the old check and passes on the fix.

**Secondary bug (evening TypeError):** Some triage cases have no `triage_at`. Several paths set a case to `triage` without running the transition flow that sets it: the reopen and triage Slack button handlers, and the `(_, CaseStatus.triage)` branch of the transition dispatcher. Subtracting `None` raised a TypeError, which the per-case `try` caught, so those cases were skipped. The fix counts from `created_at` when `triage_at` is missing, with tests for both cases. The 24 error lines in the logs don't include case IDs, so I couldn't confirm which path produced each one.

**Open items:**
- The root cause of the missing `triage_at` (the flow bypasses) is not fixed, only worked around.
- `FIRST_MISSED` is the first Monday after the deploy. The logs show no close reminders that day, but I can't confirm from the logs that there were eligible cases.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at