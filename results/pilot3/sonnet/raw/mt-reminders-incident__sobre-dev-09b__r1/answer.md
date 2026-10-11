## Recap

**Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (2025-08-12), moved the Monday test into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` use the helper, so neither could send. `case_triage_reminder` has no day check, which is why the daily reminders were unaffected.

**Deploy:** the scheduler and web pods restarted on 2025-08-13 at about 16:40Z on image `registry.example.com/dispatch:main-81d8ae42`. The previous image, `main-b05613b5`, did not contain the commit. The logs show no other deploy in the 07-28 to 08-20 window.

**Evidence:** "Case close reminder sent" lines appear only on the Mondays 07-28, 08-04 and 08-11. There are none on 08-18, the first Monday after the deploy. I only had logs through 08-20, so I couldn't check later Mondays.

**Fixes (uncommitted in the working tree):**
- `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`.
- The nightly TypeError came from `case_close_reminder` subtracting `case.triage_at`, which is `None` for some triage cases. The job now counts from `case.created_at` when `triage_at` is missing.
- `tests/case/test_case_scheduled.py` covers the weekday and fallback cases. It fails on the old code. The `tests/case` suite passed (32 tests) when I last ran it. I didn't run the full test suite.

**Open items:**
- I haven't found out why those triage cases lack `triage_at`.
- `case_stable_reminder` skips cases with no `stable_at`, so those cases still get no reminder.
- Nothing is committed or deployed yet, so production is still affected until the fix ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at