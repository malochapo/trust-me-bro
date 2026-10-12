**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py:31-33`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, but `isoweekday()` numbers Monday as `1`. The helper never returns true on any day, so the `q >= 1 and _is_reminder_day()` condition in both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) never passes. No exception is raised and nothing is logged. The daily triage reminder doesn't use the helper, which is why it kept arriving.

The correct comparison is `date.today().weekday() == calendar.MONDAY`, or `isoweekday() == 1` as before. I haven't changed anything.

**Deploy that shipped it:** the scheduler and web pods were replaced at about 2025-08-13 16:40Z with image `registry.example.com/dispatch:main-81d8ae42`.
- The log lines are `scheduler-mhtsgqwwx-q5q2n [kubelet] Started container ... main-81d8ae42` and the matching `web-5dkmr9s9s` line.
- The previous image, running from 2025-07-30 17:10Z, was `main-b05613b5`.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)". `c509d45e` is an ancestor of it, so it went out with the 28 other commits in `b05613b5..81d8ae42`.

**Evidence from the logs:**
- **Before the deploy:** on Monday 2025-08-04 and Monday 2025-08-11 at 18:00Z the old pod logged a burst of "Case close reminder sent to …" lines. On 08-04 that was 5 recipients, and on 08-11 it was 5 more.
- **After the deploy:** on Monday 2025-08-18 there were none. Only the triage and incident close reminders went out.
- **Line numbers:** the traceback for `case_close_reminder` moved from `scheduled.py` line 43 to line 47 after the deploy, which matches the 4 lines the refactor added.

**Not the cause:**
- **`stable_at` errors:** the daily `TypeError ... NoneType` from `case_stable_reminder` ran from the first day of the logs until 08-12. It was fixed by `32fa810f` (#6179) in the same deploy, so those errors vanish on 08-13.
- **`triage_at` errors:** the `case_close_reminder` `triage_at is None` errors continue after the deploy, but they are logged and skipped per case. They are a separate, pre-existing problem with some cases that have no `triage_at`.
- **Slack lookups:** the Slack `users_not_found` warnings are unrelated.

If you want, I can fix the helper and add a unit test that checks it returns true on a Monday.

----- next turn -----

Fixed and tested: the new tests pass with the fix and fail (3 failures) without it.

**Cause:** commit c509d45e ("share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compares `date.today().isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0). That is never true, so `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) stopped sending anything. Before the refactor the code was `isoweekday() == 1`.

**Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` checks the day check for all 7 weekdays. It also runs both reminder tasks on a Monday, Tuesday and Sunday and asserts the reminder is sent only on Monday.

**Evidence from the logs:**
- The commit's changes first ran in the 2025-08-13 deploy, image `main-81d8ae42`. The earlier image, `main-b05613b5`, does not contain it.
- Monday 2025-08-11 had 5 "Case close reminder sent" lines, from the old image.
- Monday 2025-08-18 had none, only the triage reminder and the incident reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18