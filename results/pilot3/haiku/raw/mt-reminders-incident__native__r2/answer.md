Here is the recap for the incident report. Nothing is committed yet.

**What happened**

- **Weekly reminders stopped after the 2025-08-13 deploy.** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The condition was never true, so neither the triage nor the stable weekly reminder was sent. The bug came in with the refactor `c509d45e` on 2025-08-12. The image `main-81d8ae42` contains that commit and started on the scheduler and web pods on 2025-08-13 at 16:40. The last weekly sends were on Monday 2025-08-11, before the deploy. None were sent on 2025-08-18 or later in the logs. Fixed by using `weekday()`, with a regression test.
- **Evening TypeError (16 nights, 2025-07-28 to 2025-08-12).** `case_close_reminder` subtracted `triage_at` from the current time. Some triage cases had `triage_at` NULL, so the subtraction raised, and the per-case `try/except` logged it and skipped the case. The likely source is `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py`, which sets the triage status without calling the flow that writes `triage_at`. I haven't confirmed this against production data. The job now counts from `created_at` when `triage_at` is missing, with tests.
- **Also fixed by the same deploy:** the stable reminder's `NoneType` errors came from missing `stable_at` values. `32fa810f` added the guard and shipped in `81d8ae42`. The errors stop after 2025-08-12.

**Open items**

- The stable reminder still skips cases with no `stable_at`, so those cases get no stable reminder. I haven't added a fallback there.
- The reopen handler still skips the triage flow. I haven't changed it.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```