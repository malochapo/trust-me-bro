**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) swapped the Monday check for one that is never true.

- **Before:** `date.today().isoweekday() == 1`. `isoweekday()` numbers Monday as 1.
- **After:** a new helper in `src/dispatch/case/scheduled.py:31` does `date.today().isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is 0, because the `calendar` module counts from Monday = 0. `isoweekday()` only returns 1 to 7, so the check is false on every day.
- **Effect:** `case_close_reminder` (triage cases) and `case_stable_reminder` both gate on this helper. Neither has sent a reminder since. The daily `case_triage_reminder` doesn't use it, so it is unaffected. That matches what you're seeing.

**The deploy that shipped it:** the scheduler and web pods were rolled out at 2025-08-13 16:40Z. The image changed from `dispatch:main-b05613b5` to `dispatch:main-81d8ae42` in both logs. Checked with git:
- `81d8ae42` contains `c509d45e`; `b05613b5` does not.
- The commit was merged on Aug 12, with only two later commits in the build.

**Log evidence:**
- Close reminders went out on Monday 07-28 (5), 08-04 (7) and 08-11 (6). The 08-11 run was on the old image.
- On Monday 08-18, the first Monday on the new image, there were none. The only "close reminder sent" line that day was the incident one, not the case one.
- The first Monday after the deploy is 08-18, which fits "since mid-August".
- The logs run to 08-20, so I can't say what happened on later Mondays.

**Unrelated noise:**
- `unsupported operand ... NoneType` errors from cases with no `triage_at`. They appear before and after the deploy (07-28, 08-13, 08-18), and they are caught per case.
- A DB restart error on 08-15 at 14:40–14:43Z.

The fix, when you want it, is to compare against `1` or use `calendar.MONDAY` with `date.today().weekday()`. I haven't changed any code.

----- next turn -----

Assignees stopped getting the Monday reminders because `_is_reminder_day()` in `src/dispatch/case/scheduled.py` could never be true. It compared `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, where Monday is 0. I changed it to `date.today().weekday()`.

**Test:** `tests/case/test_case_scheduled.py` freezes the date across a Sunday-to-Saturday week and checks that only the Monday returns true. All 7 cases pass with the fix. With the fix stashed, the Monday case fails; the other six pass because the old check was false on every day.

**Evidence from the logs:**
- "Case close reminder sent" lines appear only on Mon 2025-07-28, 08-04 and 08-11. None appear after that.
- Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) introduced the bad helper. It is contained in the image deployed on 2025-08-13 (`main-81d8ae42`), but not in the earlier `main-b05613b5` image.
- The first Monday after that deploy was 2025-08-18, and no close reminder was sent.

**Not fixed:** the logs also show repeated `datetime - NoneType` errors in `case_close_reminder`, from `case.triage_at` being `None`. That is a separate bug from the weekday one and predates it, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18