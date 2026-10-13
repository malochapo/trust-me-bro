Recap for the weekly report.

**Investigation 1: missing Monday reminders (long-running triage and stable cases)**

The weekly reminder check in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. Commit `c509d45e` introduced it on 2025-08-12. It shipped in image `dispatch:main-81d8ae42`, started 2025-08-13. The first Monday without reminders was 2025-08-18. The fix switches the check to `date.today().weekday()`, and a regression test covers all seven weekdays. It fails on the old code and passes on the fixed code.

The same job also logged a `TypeError` every evening. Some cases have no `triage_at`, because only one transition path sets it, and the job subtracted it from the current time. Those cases were silently skipped. The job now counts from `created_at` when `triage_at` is missing, with three tests.

**Investigation 2: deduplication and snoozing**

- **Dedup windows:** commit `917a0b7b` (2025-08-14) changed the custom dedup window from minutes to seconds. The UI sets windows in minutes, so a window of 30 became 30 seconds. The fix reads the stored value as minutes again, so existing filters need no edits. Two regression tests cover this, and one fails on the old code.
- **Snoozing:** commit `086dc910` (2025-08-07) changed the expired-snooze check from `continue` to `break`. An expired filter then stopped the loop, so valid snooze filters listed after it never applied. The fix restores `continue`, with a regression test that fails on the old code.
- **Canary signals:** commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated or used as dedup matches. This was a deliberate fix. It is not part of the regression, so I didn't change it.
- **Default grouping:** signals without a filter are grouped over 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`). The `filter_signal` docstring said 1 hour, and I corrected it.

Test status: the full suite has 372 passed, 4 skipped and 8 failed. The 8 failures are in `tests/ai`, `tests/database` and `tests/entity`, and they also fail on the original code. Nothing is committed or deployed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES