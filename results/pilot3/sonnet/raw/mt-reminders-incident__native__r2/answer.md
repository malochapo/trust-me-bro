**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.
- **Weekday bug:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added the helper `_is_reminder_day()`, which compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check is never true. Both `case_close_reminder` and `case_stable_reminder` skip every case, and nothing is logged. The daily triage job doesn't use the helper, so it kept working.
- **Deploy:** the production redeploy on 2025-08-13 at about 16:40 UTC moved the scheduler and web pods from `main-b05613b5` to `main-81d8ae42`, which contains that commit.
- **Evidence:** "Case close reminder sent" appears 4 times on 07-28, 6 on 08-04 and 5 on 08-11. It never appears on 08-18. On 08-18 the jobs ran in about 0.03–0.05 s and sent nothing.
- **Fixes, in the working tree and not committed:**
  - `_is_reminder_day()` now uses `weekday()`.
  - `case_close_reminder` now counts from `triage_at`, or from `created_at` when `triage_at` is missing.
  - `tests/case/test_case_scheduled.py` adds regression tests for both. All 25 tests in `tests/case` pass.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only set by the new → triage transition, so cases created directly in triage have none. That raised the error every evening, and those cases never got reminders.
- **Open items:**
  - The fixes still need deploying.
  - Mondays after 08-13 were missed, so a one-off run may be needed.
  - `case_stable_reminder` silently skips cases with no `stable_at`, since `32fa810f`. I left that alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at