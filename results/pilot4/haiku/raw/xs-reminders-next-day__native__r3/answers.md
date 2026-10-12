**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check. The old code was `date.today().isoweekday() == 1`. The refactor moved it into a helper that compares against `calendar.MONDAY`:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Monday is 0 in Python's `calendar` module). The condition is therefore never true, so `case_close_reminder` and `case_stable_reminder` never send anything. I confirmed both values locally. The daily `case_triage_reminder` doesn't call this helper, which is why triage reminders kept going out.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13 16:40Z (`scheduler-mhtsgqwwx-q5q2n`). That image's history includes `c509d45e`. `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)".

**What the logs show:**
- Case close reminders were sent on Mondays 07-28, 08-04, and 08-11, all under the previous pod (`xdp7k6gs2q`, image `main-b05613b5`).
- The next Monday, 08-18, had no case close reminders. The only close reminder that day was an incident one, from the new pod.
- Case triage reminders kept running daily through 08-20.

**Separate issue, also fixed by that deploy:** `case_stable_reminder` raised `unsupported operand type(s) ... 'NoneType'` every day from 07-28 to 08-12 because some cases have no `stable_at`. Commit `32fa810f` ("fix(scheduler): not all cases have a stable_at date", 08-11) added the `if case.stable_at:` guard, and the errors stop after the 08-13 deploy. That fix doesn't affect the Monday regression. Stable-case reminders were already failing on Mondays before this, and they'll stay silent until the weekday check is fixed.

I haven't changed any code. When you're ready, the fix is to compare against `1` (or use `date.today().weekday() == calendar.MONDAY`, which is the same check). A test that pins the reminder day to a known Monday would catch this if it regresses.

----- next turn -----

The Monday reminders were broken by a weekday comparison in `_is_reminder_day`. I fixed it and added regression tests. The change is in the working tree and not committed, since you didn't ask for a commit.

**Cause:** `_is_reminder_day` compared `date.today().isoweekday()` (Monday is `1`) to `calendar.MONDAY` (which is `0`). The check could never pass, so `case_close_reminder` and `case_stable_reminder` never sent on Mondays. The scheduler logs match this: Monday 2025-08-04 sent 6 case reminders and Monday 2025-08-11 sent 5, but Monday 2025-08-18 sent none. The deploy `main-81d8ae42` (2025-08-13) contains the bad commit, and the previous deploy `main-b05613b5` does not.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` → `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. One line.
- `tests/case/test_case_scheduled.py` (new):
  - `test_is_reminder_day` checks Monday is true and Sunday/Tuesday are false.
  - `test_case_stable_reminder_only_sends_on_monday` runs the real stable-reminder body on a pinned Monday and a pinned Tuesday.
- The new tests fail on the original code (3 failures) and pass with the fix.

**Test results:** `python -m pytest` gives 365 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`. They also fail on the original code, so they predate this change. `ruff` isn't installed here, so I didn't lint.

**Not changed:** the scheduler also logs a `None` subtraction error in `case_close_reminder` for triage cases with no `triage_at`. Those cases are skipped, and this error did not cause the missed Mondays, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18