**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check.

- **The bug:** the commit replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1 through Sunday as 7. `calendar.MONDAY` is 0, because the `calendar` module numbers days from Monday = 0. The helper therefore never returns true, since `isoweekday()` is never 0. The weekly reminder is skipped on every day, including Mondays.
- **What it affects:** `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both call the helper. The incident reminder (`incident/scheduled.py:229`) still uses the literal `== 1`, so it was untouched. The daily triage reminder doesn't use the helper either. That matches what you're seeing.
- **Evidence from `scheduler.log`:**
  - Close reminders were sent on Mondays 07-28, 08-04 and 08-11. Each of those evenings has several "Case close reminder sent to …" lines.
  - On Monday 08-18 at 18:00, `case_stable_reminder` finished in 0.026s with no sends. No "Case close reminder sent" line appears that day. The incident close reminder was still sent.
  - The traceback line numbers in the log shifted from 43/51 to 47/55 on 08-18. That is consistent with the extra helper lines being added to the file.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started 2025-08-13 at about 16:40Z.

- Both the scheduler (pod `scheduler-mhtsgqwwx-q5q2n`) and the web pod (`web-5dkmr9s9s-xxktx`) started that image at that time.
- It replaced `main-b05613b5`, which had been running since 2025-07-30 and is the image that sent the 08-04 and 08-11 reminders.
- `81d8ae42` ("fix(case): exclude resolved_by in update") is the commit the image was built from. `c509d45e` is an ancestor of it, which I confirmed with `git merge-base --is-ancestor`. It is not in `b05613b5`.
- The 08-11 Monday run happened on the old image, and 08-18 is the first Monday on the new one. So the first missed reminder was 08-18, and the bug shipped on 08-13.

**Unrelated errors in the log:** the `TypeError: datetime - NoneType` from `case_close_reminder` appears every day, including before the deploy. It comes from a triage case with a null `triage_at`. It is caught per case and has no connection to the missing reminders. Reminders were still sent on 07-28, 08-04 and 08-11 despite it.

I haven't changed any code. The fix would be to compare against 1 (the old literal) or `calendar.MONDAY + 1`. The cleaner option is `date.today().weekday() == calendar.MONDAY`. A small unit test for `_is_reminder_day()` would also have caught this. Want me to make the change?

----- next turn -----

Weekly case reminders are fixed: `_is_reminder_day()` now returns true on Mondays again. The new test fails on the old code and passes on the fix, and I haven't run the rest of the suite.

**Cause:** commit `c509d45e` ("share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The old inline check was `isoweekday() == 1`. The new one compared `isoweekday()` to `calendar.MONDAY`, which is 0. `isoweekday()` returns 1 for Monday, so the check was never true. `case_close_reminder` and `case_stable_reminder` both depend on it.

**Fix:** the check now uses `weekday() == calendar.MONDAY`, so both sides use the same numbering.

**Test:** `tests/case/test_case_scheduled.py` freezes the date across a full week plus the following Monday and asserts the check is true only on Mondays. With the fix reverted, the two Monday cases fail.

**Logs:** "Case close reminder sent" appears on Mondays 2025-07-28, 08-04 and 08-11, and never after the deploy on 08-13. The deploy was image `main-81d8ae42`, which contains `c509d45e`. The previous image, `main-b05613b5`, does not.

**Separate issue, not fixed:** `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime' and 'NoneType'` every day. It comes from cases in triage with no `triage_at`. It is caught per case, so it doesn't block other reminders, and it started before the regression.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18