**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12 14:05 PDT) broke the Monday check.

It replaced the inline `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1 through Sunday as 7. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0. So the helper compares against 0, which `isoweekday()` never returns, and it is always False. Both `case_close_reminder` (triage) and `case_stable_reminder` call the helper, so neither ever sends the weekly reminder. The daily triage reminder (`case_triage_reminder`) doesn't use it, which is why those still arrive.

**Evidence in the logs:**
- The "Case close reminder sent to …" lines in `scheduler.log` appear only on Mondays before the change: 4 on 07-28, 6 on 08-04 and 5 on 08-11.
- There are none on Monday 08-18. The 18:00 run of both case jobs executes, but sends nothing.
- On 08-18 the triage reminder still goes out (`Case triage reminder sent to l.nguyen@…`).

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is `fix(case): exclude resolved_by in update (#6183)`, 2025-08-12 14:47 PDT.
- It rolled out on 2025-08-13 at 16:40:06Z (scheduler pod `scheduler-mhtsgqwwx-q5q2n`) and 16:40:07Z (web pod).
- The previous image was `main-b05613b5`, running since 07-30.
- `git merge-base --is-ancestor` confirms `c509d45e` is an ancestor of `81d8ae42`, so this image is the first to contain it.
- The commit that gave the image its tag is unrelated. The refactor came in as an ancestor.
- 08-18 is the first Monday after the rollout and has no reminders.

**Unrelated noise:** the log also shows a daily `unsupported operand type(s) for -: datetime and NoneType` error in these jobs. That is a separate, older problem from cases with a null `stable_at` or `triage_at`. It was already present before the deploy, and the 08-11 reminders went out despite it. Commit `32fa810f` ("not all cases have a stable_at date") looks related. It does not explain the missing reminders.

**Suggested fix, not applied:** compare against `isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. I'd also add a test for `_is_reminder_day()` that mocks a Monday. Cases that crossed the one-week mark during the outage will still get their reminder on the next Monday after the fix ships.

----- next turn -----

I fixed the bug and added a regression test. The test fails on the old code and passes on the fix.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. The close and stable reminders in `src/dispatch/case/scheduled.py` both call it, so neither fired again. I changed it to `weekday()`, which matches `calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks that a Monday returns True and a Tuesday and a Sunday return False. It only covers `_is_reminder_day()`, not the two reminder jobs themselves. I ran only that file, not the full suite.

**Timeline:**
- Commit `c509d45e` ("share the weekly reminder check", Aug 12) introduced the bug. It replaced the inline `isoweekday() == 1` with the helper.
- The scheduler image `main-81d8ae42` shipped it. That commit contains `c509d45e`, and the scheduler started on that image on 2025-08-13 at 16:40Z.
- The scheduler log shows close reminders sent on Jul 28, Aug 4 and Aug 11, and none on Aug 18.

**Not fixed:** the logs also show a repeated error, `datetime - NoneType`, at `case.triage_at` in `case_close_reminder` (line 47 on Aug 18). It predates the weekday bug, and the per-case `try/except` stops it blocking other cases. I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18