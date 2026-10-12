## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced an inline `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`. The helper compared `isoweekday()` to `calendar.MONDAY`. Those use different numbering: `isoweekday()` gives Monday as 1, and `calendar.MONDAY` is 0. The comparison was never true, so `case_close_reminder` and `case_stable_reminder` silently sent nothing. `case_triage_reminder` doesn't use the helper, which is why the daily reminders were unaffected. No error was logged.

**Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on 2025-08-13 at about 16:40 UTC. It is the first image containing `c509d45e`.

**Timeline:**
- Monday 2025-08-11 was the last Monday on the old image. 6 case close reminders went out.
- Monday 2025-08-18 was the first Monday on the new image. 0 went out.
- Monday 2025-08-04 had 7 and 2025-07-28 had 4, both on the old image.

**Secondary bug (the evening `TypeError`):** `case_close_reminder` subtracted `case.triage_at` without a None check. `triage_at` is only set when a case goes through the triage transition flow, so cases in triage status that never went through it have it NULL. The error was logged once each evening from 2025-08-13 on, and it was caught per case, so other cases weren't affected. Before the Monday fix it was masked by the always-false Monday check.

**Changes (uncommitted):**
- **Monday fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.
- **Fallback fix:** the same file now counts the age from `case.triage_at or case.created_at`.
- **Tests:** `tests/case/test_case_scheduled.py` is new. It checks the helper on frozen dates and runs both weekly jobs on a Monday and a Tuesday. It also covers the `created_at` fallback. With the source fixes stashed, 6 of its 11 tests fail. With the fixes, all of `tests/case` passes (26 tests).

**Not done:** nothing is committed or deployed, so reminders resume only after a deploy. The next confirmation is the first Monday 18:00 run afterwards. I also didn't find out why those cases have a NULL `triage_at`, because the logs don't identify them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at