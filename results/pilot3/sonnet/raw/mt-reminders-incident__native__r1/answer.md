## Recap

**Weekly reminder outage**
- **Symptom:** assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`, which compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1 and `calendar.MONDAY` is 0, so the check was never true. `case_close_reminder` and `case_stable_reminder` both use it and skipped every case. `case_triage_reminder` has no weekday gate, which is why it still worked.
- **Deploy:** the kubelet "Started container" lines in the logs give the image tag. At about 2025-08-13 16:40Z both the scheduler and the API moved from `main-b05613b5` to `main-81d8ae42`. I confirmed with git that `c509d45e` is in `81d8ae42` and not in `b05613b5`. In my first answer I said the logs recorded no SHA. That was wrong, because I hadn't found those lines.
- **Evidence:** reminders were sent on Mondays 07-28, 08-04 and 08-11, all by the old pods. On 08-18 the jobs ran but sent nothing. Traceback line numbers in `scheduled.py` shifted by 4 after the deploy, matching the new code.
- **Fix:** it uses `weekday()` with `calendar.MONDAY`. The regression tests cover each day of the week and both reminder jobs.

**Evening TypeError**
- **Cause:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for some triage cases. `triage_at` is only set by `case_triage_status_flow`. Cases created directly in triage, or moved into triage from a state other than new or closed, never get it. I haven't confirmed from the data which of these produced the affected cases.
- **Fix:** the job now counts from `triage_at or created_at`. Tests cover a missing `triage_at` on an old case and on a recent one.

Both fixes and `tests/case/test_case_scheduled.py` are in the working tree and not committed. `tests/case` passes (28 tests).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at