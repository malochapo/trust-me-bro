## Recap

**Weekly reminders stopped (root cause).** Commit `c509d45e` (2025-08-12) was a refactor that moved the Monday check into a helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`. The old inline check was `isoweekday() == 1`. The helper compared `isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1 and `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use the helper, so neither could send its weekly reminder again. The daily triage reminder doesn't use it and kept working. I changed the helper to use `weekday()`, which also numbers Monday as 0.

**Deploy.** Image `registry.example.com/dispatch:main-81d8ae42` rolled out around 2025-08-13 16:40 UTC. The scheduler and API pods were replaced at that point. The previous image, `main-b05613b5` (2025-07-30), did not contain `c509d45e`. Reminders were sent on 07-28, 08-04 and 08-11, and none on 08-18, although the 18:00 job ran that day.

**Evening TypeError (separate, older issue).** `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set when a case transitions into triage, so cases created in triage or predating the column have `None`. The subtraction failed, the per-case `try/except` logged it, and the case was skipped, so those cases never got a reminder. The job now counts from `created_at` when `triage_at` is missing.

**Tests.** `tests/case/test_case_scheduled.py` holds 11 tests that pass with the fixes. They cover the Monday and non-Monday behavior and the `created_at` fallback. I haven't run the rest of the suite or committed anything.

**Open item.** `case_stable_reminder` still silently skips stable cases that have no `stable_at`. I didn't change it because it wasn't in scope.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at