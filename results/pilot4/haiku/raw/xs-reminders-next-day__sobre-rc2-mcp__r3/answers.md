**Root cause:** commit `c509d45e` broke the Monday check. The Monday gate now compares against `calendar.MONDAY`, which is 0 in Python (Monday = 0), but `date.today().isoweekday()` returns 1 for Monday. So `_is_reminder_day()` is always False.

**The change** (`src/dispatch/case/scheduled.py`, the `_is_reminder_day` helper):

```python
# before (c509d45e^)
if q >= 1 and date.today().isoweekday() == 1:
# after
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # calendar.MONDAY == 0
```

I confirmed `calendar.MONDAY == 0` and that `isoweekday()` of 2025-08-18 is 1, so the comparison is False.

**Why the symptoms match:**
- `case_stable_reminder` (weekly stable reminders) and `case_close_reminder` (weekly triage-close reminders) both call `_is_reminder_day()`, so both stopped sending.
- `case_triage_reminder` (the daily "triage" reminder for new cases) never uses the weekday gate, so it still runs. That's the daily reminder that still arrives.
- The last successful stable/close reminders were on Monday 2025-08-11 18:00 UTC (`scheduler.log:16808`). On Monday 2025-08-18, the scheduler sent only triage reminders and no close/stable reminders.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42`, which includes `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check"). It was rolled out to the scheduler pod `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13 16:40:06 UTC (`scheduler.log:18851`). The web pod was updated to the same image at the same time (`api.log:13201`). The earlier image `main-b05613b5` was running on 2025-07-30 through the window before this, and it still ran the old `== 1` check.

**Side finding (not the cause):** `case_close_reminder` has been logging `unsupported operand ... NoneType` on `case.triage_at` since 2025-07-28 (`scheduler.log:785`, `:15474`, `:24277`). It is caught per case, so it doesn't block other cases, but it is the same kind of missing-timestamp guard that `32fa810f` added for `stable_at`. The triage path has no such guard.

**Suggested fix (not applied, per your request):** make the gate compare against the same convention the code used before, i.e. `date.today().weekday() == calendar.MONDAY` (`weekday()` is Monday = 0), or restore `isoweekday() == 1`. Add a guard for `triage_at` in the same pass. A test that pins a known Monday would catch this class of regression.

Nothing in the repo was changed.

----- next turn -----

The Monday reminders were broken by a one-line weekday mismatch, and I've fixed it. The fix is in the working tree and not committed.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so the close and stable reminders were silently skipped every week. The bad line came in with `c509d45e` on Aug 12, 2025. It was refactored out of the previous `isoweekday() == 1` check, which was correct.

**Evidence from the logs:**
- Image `main-b05613b5` was running through Aug 13 and still had the correct check. Reminders were sent on Monday Aug 11 (for example, "Case close reminder sent to …" at 18:00).
- Image `main-81d8ae42` (which contains `c509d45e`) started on Aug 13.
- On Monday Aug 18, both reminder jobs ran at 18:00 and sent nothing. The same is true for Aug 25 and Sep 1.

**Fix:** `date.today().weekday() == calendar.MONDAY`, which compares like with like.

**Regression test:** `tests/case/test_case_scheduled.py` freezes "today" to each day of one week and asserts `_is_reminder_day()` is true only on Monday. Against the old code it fails on Monday and passes on the other six days. With the fix, `python -m pytest tests/case` gives 22 passed.

I didn't commit. Note that the Aug 18 run also logged a per-case error in `case_close_reminder` (`datetime - NoneType` on `triage_at`). It's caught per case, so it doesn't block other cases, but cases with no `triage_at` will never get a reminder. I left that alone since it's a separate issue.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18