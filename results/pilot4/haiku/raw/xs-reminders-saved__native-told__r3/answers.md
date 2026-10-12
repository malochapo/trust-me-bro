**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday-based index). The comparison is therefore always false, so `case_close_reminder` and `case_stable_reminder` never send. The daily triage reminder has no weekday gate, which is why it still arrives. The reminder settings didn't change.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which contains `c509d45e`. The kubelet "Started container" lines show it rolled out to the scheduler and web at 2025-08-13T16:40:06Z (`scheduler.log:18851`, `api.log:13201`). The previous image, `main-b05613b5`, started 2025-07-30.

**Evidence from the logs:**
- Monday 2025-08-04 sent 6 close reminders and Monday 2025-08-11 sent 5, both before the deploy.
- Monday 2025-08-18 sent 0. The triage reminder still ran daily.

**Side finding, not the cause:** since 2025-07-28, `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` daily at `scheduled.py:47` when `triage_at` is None. The per-case try/except swallows it, so other cases still get processed. It predates the regression and doesn't explain the missing Monday sends.

**Suggested fix (not applied, per your instruction):** make the helper compare against Monday's value (`date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`). A test that pins the reminder day to a Monday would have caught this.

I also saved these findings to the project memory so a later session can pick them up.

----- next turn -----

I saved the findings to project memory, so tomorrow's session can pick them up from `weekly-case-reminder-regression.md` (indexed in `MEMORY.md`).

What's recorded:
- **Root cause:** commit `c509d45e` replaced `isoweekday() == 1` with `isoweekday() == calendar.MONDAY`, and `calendar.MONDAY` is 0. The Monday check is never true, so weekly close and stable reminders stop. Daily triage reminders have no weekday gate, so they are unaffected.
- **Deploy:** image `main-81d8ae42`, which contains `c509d45e`, started on 2025-08-13 16:40Z.
- **Pre-existing noise:** `case_close_reminder` logs a `datetime - NoneType` error daily when `triage_at` is None. It predates the regression and is swallowed per case.
- **Status:** investigation complete. No code changed, no commits, no tests run.
- **Next steps:** apply the fix (comparing against Monday's value, for example `date.today().weekday() == calendar.MONDAY`), add a test that pins the reminder day to a Monday, and optionally guard the `triage_at` None case.

The memory note links to `[[case-reminder-scheduling]]`, which doesn't exist yet. I marked that in the note.

----- next turn -----

The weekly Monday reminders are fixed in the working tree, with a regression test. I did not commit.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The check was never true, so the weekly close and stable reminders stopped. The daily triage reminder has no weekday gate, so it was unaffected. The logs agree: the last Monday with sends was 2025-08-11 (5 close reminders and 1 stable), and 2025-08-18 sent none.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` also counts Monday as 0, so it matches the constant.

**Regression test:** `tests/case/test_case_scheduled.py` pins "today" across a full week and checks that only Monday returns true. It fails on the buggy code for Monday, and passes after the fix.

**Results:** the case tests pass (22). The full suite has 8 failures in `tests/ai/test_ai_service.py` and two service tests. All 8 also fail on the original code, so they are unrelated to this change.

I also updated the saved memory note to match this state.

Not changed: `case_close_reminder` still computes `datetime.utcnow() - case.triage_at` without a None check, which produces the daily `datetime - NoneType` errors in the logs. The stable reminder already guards against this. It's a separate issue, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18