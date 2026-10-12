Fixed: the weekly case reminders now check for Monday correctly. The new test passes, and I confirmed on the pre-fix code that it would have failed. I did not run the rest of the suite.

**Cause.** Commit c509d45e moved the Monday check into `_is_reminder_day()`. That function compared `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, which is 0. So the check was true on Tuesdays and never on Mondays. Both the close reminder (triage cases) and the triage reminder (stable cases) use it.

**Fix.** In `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. I added `tests/case/test_case_scheduled.py`, which checks the function on Mondays, a Tuesday and a Sunday.

**Evidence from the logs.**
- Close reminders went out on 2025-07-28, 08-04 and 08-11, all Mondays.
- The scheduler restarted on image `main-81d8ae42` on 2025-08-13.
- After that restart, reminders went out every day from 08-13 to 08-20 instead of only on Mondays. That fits the fix landing in that image, but I did not check which commits the image contains.
- The first Monday without reminders was 2025-08-18.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18