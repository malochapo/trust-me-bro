**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

- **Before:** the stable and triage close reminders tested `date.today().isoweekday() == 1`. `isoweekday()` numbers Monday as 1.
- **After:** the refactor moved the test into `_is_reminder_day()`, which compares `isoweekday()` with `calendar.MONDAY`. `calendar.MONDAY` is 0 (the `calendar` module counts weekdays from Monday = 0). I confirmed that value by running it.
- **Effect:** `isoweekday()` only returns 1 to 7, so the check is never true. `case_close_reminder` (triage cases) and `case_stable_reminder` still run every day at 18:00 but never send. They don't log an error, so nothing alerted.
- **Why the daily triage reminders still work:** `case_triage_reminder` doesn't use that check.

**Evidence in the logs:**

| Monday | "Case close reminder sent" lines |
|---|---|
| 2025-07-28 | 4 |
| 2025-08-04 | 6 |
| 2025-08-11 | 5 |
| 2025-08-18 | 0 |

"Case triage reminder sent" still appears on 08-18, 08-19 and 08-20.

**The deploy that shipped it:**
- **Image:** `registry.example.com/dispatch:main-81d8ae42`.
- **When:** both the scheduler and the web pods restarted on it at 2025-08-13 ~16:40Z. The previous image was `main-b05613b5`, running since 07-30.
- **Why it contains the bug:** `81d8ae42` ("fix(case): exclude resolved_by in update", #6183) comes after `c509d45e` on main.
- **Last deploy without it:** 08-11 was the last Monday before the bug, and it ran on `main-b05613b5`.
- **Other commits in that deploy:** `6c56558c`, `7c446bd6` and `81d8ae42`.
- **Not in it:** `3d3bf623` and later came after `81d8ae42`.
- **Limit of the evidence:** the logs only name the image tag. I'm inferring the contents from git ancestry, not from the build itself.

**Unrelated errors in the logs:** `case_stable_reminder` and `case_close_reminder` raised `unsupported operand ... NoneType` every day from 07-28 to 08-12, from cases with no `stable_at` or `triage_at` date. The `stable_at` side was fixed by `32fa810f` and the errors dropped to two a day after the 08-13 deploy. That is a separate bug and not why reminders stopped, since Monday sends still went out on 08-04 and 08-11.

The fix is to compare against `isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. I haven't changed any code, as you asked.

----- next turn -----

I saved the findings to memory as `weekly-case-reminder-outage.md`, with a pointer in `MEMORY.md`.

It records:
- **Root cause:** commit `c509d45e` compares `isoweekday()` (Monday is 1) with `calendar.MONDAY` (0), so the Monday check never passes.
- **Deploy:** image `main-81d8ae42`, rolled out around 2025-08-13 16:40Z.
- **Evidence:** reminders were sent on Mondays 07-28, 08-04 and 08-11 and not on 08-18.
- **Next step:** the fix, plus a test for `_is_reminder_day`.

The `triage_at` NoneType error in `case_close_reminder` is also in the note. The `stable_at` side of that error was fixed by `32fa810f`. I didn't change any code.

----- next turn -----

I fixed the weekday check and added a regression test; I haven't committed anything. The new test passes (3 cases). I didn't run the rest of the suite.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. The close and stable reminders ran daily and never sent anything, with no error logged.

**Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` on a Monday (2025-08-18, expects true), a Tuesday and a Sunday (expect false). The old code fails the Monday case.

**Triage-time bug not fixed:** the separate `NoneType` error in `case_close_reminder` still exists. Cases with no `triage_at` raise an error there, and it was still showing up in the logs after the deploy. I left it alone since it's a different bug. Say if you want it fixed too.

The deploy contents are inferred from git ancestry, since the logs only show the image tag.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18