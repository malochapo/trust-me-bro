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