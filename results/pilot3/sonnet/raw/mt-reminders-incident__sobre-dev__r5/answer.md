**Recap**

- **Symptom:** from mid-August the weekly Monday reminders for long-running triage and stable cases stopped. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the inline check `date.today().isoweekday() == 1` with a helper, `_is_reminder_day()`. The helper compares `isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check never matched. It affected the `case-close-reminder` and `case-stable-reminder` jobs and logged nothing.
- **Deploy:** all API and scheduler pods were replaced on 2025-08-13 at about 16:40 UTC.
  - The scheduler logs show the container image changing from `main-b05613b5` to `main-81d8ae42`. The API logs show the same change.
  - `81d8ae42` is dated 2025-08-12 14:47 PDT, after `c509d45e` at 14:05, so I take `c509d45e` to be included. I didn't check git ancestry directly.
  - In my first answer I said the logs carried no image tag. That was wrong. The kubelet "Started container" lines do.
- **Impact:** the close reminders were sent on Mondays 07-28, 08-04 and 08-11. On 08-18, the first Monday after the deploy, none were sent.
- **Fixes (uncommitted, not yet deployed):**
  - `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`.
  - `case_close_reminder` now counts from `created_at` when `triage_at` is missing.
  - Regression tests are in `tests/case/test_case_scheduled.py`. All 14 tests pass with the fixes, and 5 fail without them.
- **Evening `TypeError`:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for some triage cases.
  - The reopen button handler in `interactive.py` sets the status to triage directly, without going through the flow that sets `triage_at`.
  - Cases from before the column was added in 2022 can also have it empty. I haven't tied either path to specific cases in the logs.
  - The error appeared daily from 07-28, before the deploy. It caused those cases to miss their reminder, but it isn't what stopped the weekly reminders.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at