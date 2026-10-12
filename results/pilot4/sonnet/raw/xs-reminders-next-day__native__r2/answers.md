**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12, Jordan Lee) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`. The helper compares `isoweekday()` to `calendar.MONDAY`.

- **Why it never fires:** `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. I confirmed that value by running it. The check is now never true on any day.
- **What it hits:** both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) use the helper. The daily `case_triage_reminder` never used it, which is why those still arrive.
- **Why it's silent:** the condition is just false, so nothing is logged and there's no error.

**The deploy:** image `registry.example.com/dispatch:main-81d8ae42` (commit "fix(case): exclude resolved_by in update (#6183)", the first commit after `c509d45e` on main). I confirmed `c509d45e` is an ancestor of `81d8ae42`.

- Both the scheduler and the web pods started that image at 2025-08-13T16:40Z.
- The previous image, `main-b05613b5` (deployed 2025-07-30), does not contain `c509d45e`.
- This is a bundled deploy: the reminder refactor reached production only because it landed alongside #6183, which is unrelated.

**Log evidence:** the close and stable reminders went out on each Monday before the deploy and not after.

| Date | "Case close reminder sent" lines |
|---|---|
| 2025-07-28 | 4 |
| 2025-08-04 | 6 |
| 2025-08-11 | 5 |
| 2025-08-18 (first Monday after the deploy) | 0 |

On 2025-08-18 only the daily triage reminder was sent.

**Separate issue (not the cause):** `case_close_reminder` still throws `TypeError: datetime - NoneType` once a day. At least one triage case has `triage_at` set to `None`, and that error appears in the logs both before and after the deploy. Commit `32fa810f` guarded the same problem for `stable_at` but not `triage_at`. Because the error is caught per case, it can stop reminders for cases after the bad one, but it didn't start in August.

**Fix, when you want it:** use `isoweekday() == 1`, or compare against `calendar.MONDAY + 1`. Using `date.today().weekday() == calendar.MONDAY` would also work. A small test for the helper would stop this recurring. I haven't changed any code.

----- next turn -----

Weekly reminders will go out on Mondays again. The new tests pass with the fix and fail on the old code (3 failures, including both Monday cases).

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. That silenced both the triage close reminder and the stable close reminder. I changed it to `date.today().weekday()`, which does use 0 for Monday.

**Regression test:** `tests/case/test_case_scheduled.py` checks that the helper is true only on Monday. It also checks that `case-close-reminder` and `case-stable-reminder` send on Monday and not on other days.

**Timeline from the logs:**
- Close reminders went out on Mondays 07-28, 08-04 and 08-11.
- Commit c509d45e, which introduced the bug, is dated 08-12.
- Image `main-81d8ae42` was deployed on 08-13, and it contains that commit.
- The first Monday after that was 08-18, and no case close reminders went out that day. Only an incident close reminder and the daily triage reminder did.

**A separate problem I did not fix:** the scheduler log shows a daily `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` error in `case_close_reminder`. A case in triage has no `triage_at` value. That is a data or logic issue that would hide reminders for that case even with this fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18