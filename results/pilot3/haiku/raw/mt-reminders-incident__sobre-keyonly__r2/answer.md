Recap of the Monday reminder incident and the fixes. Nothing is committed.

**What happened:** Weekly reminders for long-running triage and stable cases stopped after the 2025-08-11 Monday run. The daily triage reminders kept going.

**Weekday bug:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced it in a refactor that moved the check into the helper. The fix uses `date.today().weekday()`, which matches `calendar.MONDAY`. A regression test pins each weekday and fails with the bug reinstated.

**Deploy:** image `main-81d8ae42` started on the scheduler and web pods at 2025-08-13 16:40 UTC, replacing `main-b05613b5`. No close reminders went out on the next Monday, 2025-08-18.

**Evening TypeError:** `case_close_reminder` subtracted `triage_at` from the current time, and `triage_at` is NULL for some triage cases. The reopen button handler (`reopen_button_click`, `src/dispatch/plugins/dispatch_slack/case/interactive.py`) sets triage status directly without the transition flow, which is the only code that sets `triage_at`. The job now uses `created_at` when `triage_at` is missing, with tests covering that case, a recent case, and the normal case.

**Not fixed, for follow-up:**
- The reopen handler should set `triage_at` through the transition flow. I added the fallback instead, as requested.
- `created_at` defaults to a timezone-aware datetime while the job compares against naive `utcnow()`. This works for cases loaded from the database but would raise `TypeError` for in-memory cases.
- `case_stable_reminder` still silently skips stable cases with no `stable_at`.

**Report fields:**

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at