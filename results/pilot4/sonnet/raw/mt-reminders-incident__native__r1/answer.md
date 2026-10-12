**Recap**

- **Weekday bug:** commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The condition was never true. The weekly close reminders for triage and stable cases silently stopped, while the daily triage reminder kept working because it doesn't use the helper.
- **Deploy:** the image `main-81d8ae42` went out on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, did not contain the commit. The last Monday with reminders was 2025-08-11, and 2025-08-18 had none.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` without checking for `None`. That timestamp is only set on the New→Triage and Closed→Triage transitions, so cases created directly in triage never get one. The exception was caught per case, so those cases were skipped and logged an error every evening.
- **Fixes:** `_is_reminder_day()` now uses `weekday()`, and the close reminder counts from `triage_at or created_at`. `tests/case/test_case_scheduled.py` has 11 tests that pass. The two regression tests fail without the fixes. Nothing is committed.
- **Open item:** `case_stable_reminder` still silently skips cases with no `stable_at`. I did not change it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at