The root cause is a Monday check that can never be true. It shipped in the deploy of image `main-81d8ae42` on 2025-08-13. I haven't changed any code.

**Root cause**

`_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares two different numbering schemes:

```python
return date.today().isoweekday() == calendar.MONDAY
```

- `isoweekday()` returns Monday = 1.
- `calendar.MONDAY` is Monday = 0. I confirmed this with `python3 -I`.

So the condition is always False, and both `case_close_reminder` and `case_stable_reminder` never send. The per-case `q >= 1 and _is_reminder_day()` check sits inside those functions, so nothing is sent on any day.

The bug came from commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). The refactor replaced the inline `date.today().isoweekday() == 1` with this helper and changed the constant to `calendar.MONDAY`. Before that commit, the check was correct.

**The deploy that shipped it**

- Image `registry.example.com/dispatch:main-81d8ae42` (commit `81d8ae42`, "fix(case): exclude resolved_by in update (#6183)") started on scheduler pod `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40Z. `c509d45e` is in the range `b05613b5..81d8ae42`, so it went out in this deploy.
- The previous image was `main-b05613b5`, on pod `scheduler-xdp7k6gs2q`.

**Evidence from the logs**

- Monday 2025-08-11, old image: "Case close reminder sent" for several assignees (r.patel, s.lindqvist, and others).
- Monday 2025-08-18, new image: no close or stable reminders sent.
- Daily triage reminders kept arriving. They are a separate function with no weekday check, so they are unaffected.

**Unrelated noise**

`TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` shows up daily from 2025-07-28 onward in `case_close_reminder`, where `triage_at` is None. The per-case try/except swallows it, so it doesn't stop other cases. It predates the regression and is not the cause. Commit `32fa810f` added the `stable_at` guard for the same kind of problem, but nothing guards `triage_at`.

**Suggested fix (for when you want it)**

Change the comparison to `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1`. Consider guarding `triage_at` the same way `32fa810f` guarded `stable_at`. I'd also add a test that pins the day check to a known Monday.

I saved these findings to project memory so later sessions can pick them up.

----- next turn -----

The Monday weekly reminders were never sent after the 2025-08-13 deploy because of a weekday off-by-one, and that is now fixed.

**The bug:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It was never true, so `case_close_reminder` and `case_stable_reminder` skipped every Monday. Commit `c509d45e` introduced it when it replaced the inline `isoweekday() == 1` check with the helper.

**The logs confirm it:** Close reminders were sent on 2025-07-28, 2025-08-04, and 2025-08-11 (old image `main-b05613b5`, which predates `c509d45e`). The scheduler switched to `main-81d8ae42` at 2025-08-13 16:40 UTC, and no close or stable reminders were sent on 2025-08-18 or later (the log runs to 2025-08-20). Daily triage and incident reminders kept running, since they don't use this check.

**The fix:** I changed the check to `date.today().weekday() == calendar.MONDAY`. The incident scheduler's `isoweekday() == 1` check is already correct and I left it alone.

**The regression test:** `tests/case/test_case_scheduled.py` patches `date` in the scheduler module and checks `_is_reminder_day()` for each day of one week. Before the fix it failed on Monday; after the fix all seven days pass. `python -m pytest tests/case` passes (22 tests).

**Full suite:** 366 passed, 8 failed, 4 skipped. The same 8 tests fail with the fix stashed, so they are unrelated: four in `tests/ai/test_ai_service.py`, `test_restricted_case_filter_with_test_data`, and `test_find_entities_with_field_only`.

**Not changed:** `case_close_reminder` still raises a `TypeError` for cases with `triage_at` None. It's caught per case, so it doesn't block the other reminders, but it logs an error every day. The stable path was guarded in `32fa810f`, and the same guard would fix this. I didn't change it because it's outside this bug.

The changes are uncommitted in the working tree. I also updated the saved memory note with the fix status.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18