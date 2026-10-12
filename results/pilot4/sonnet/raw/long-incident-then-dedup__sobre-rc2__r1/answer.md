Two investigations today: the weekly reminders that stopped in August, and the signal snooze and deduplication bugs. Everything below is fixed in the working tree with tests, and nothing is committed.

**1. Weekly reminders stopped (long-running triage and stable cases)**
- `c509d45e` (2025-08-12), "share the weekly reminder check", moved the Monday check into `_is_reminder_day()`. It compared `date.isoweekday()`, which runs 1–7 with Monday as 1, against `calendar.MONDAY`, which is 0. The check was never true, so the weekly jobs silently never sent anything. The daily triage reminders don't use this check, which is why they kept arriving.
- It shipped in image `main-81d8ae42` (started 2025-08-13 16:40 UTC in both the API and scheduler logs). The previous image was `main-b05613b5`. The first Monday after that deploy was 2025-08-18.
- Fix: the check now uses `weekday()`, which matches `calendar.MONDAY`. A parametrized test covers every day of a week.
- Nightly `TypeError` in the close reminder: the job subtracted `case.triage_at`, which is only set when a case goes through the triage transition. Other cases have it NULL. It now counts from `triage_at or created_at`, and a test covers that. `case_stable_reminder` still skips cases with no `stable_at`. I can add the same fallback if you want it.

**2. Signal snooze and deduplication**
- Four commits since 2025-05-22 changed the decision: `a348bbd2` (canary signals are never deduplicated and are ignored as match targets), `7a9fe810` (default window made configurable, 60 minutes down to 45), `086dc910` and `917a0b7b`.
- `917a0b7b` (2025-08-14) read a filter's window as seconds, but the UI and stored data are minutes. A 30 became 30 seconds. It is fixed back to minutes, and the column and schema defaults are now in minutes. A regression test covers it.
- `086dc910` (2025-08-07) changed an expired snooze from `continue` to `break`, so a valid snooze listed after an expired one was never evaluated. It is fixed, with a regression test.
- Instances that were already split into separate cases or not snoozed during the bad periods are not repaired.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES