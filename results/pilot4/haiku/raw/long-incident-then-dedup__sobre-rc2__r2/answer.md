**Reminders (Monday case close/stable reminders)**

- The Monday check was `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday, and `calendar.MONDAY` is 0, so the check never matched. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved this check into `_is_reminder_day()`. It was deployed as `main-81d8ae42` on 2025-08-13 at 16:40 UTC.
- The logs confirm the timing. Case close reminders went out on Monday 2025-08-04 and Monday 2025-08-11, both before the deploy. The first missed Monday was 2025-08-18.
- The fix uses `date.today().weekday() == calendar.MONDAY`, with a regression test that fails on the old check. Nothing is committed.

**Evening TypeError**

- The close reminder job subtracted `case.triage_at` from the current time. For cases with no triage time, the subtraction raised `TypeError`. The per-case `try` logged it and skipped the case, so the job kept running. The error appeared every evening from 2025-07-28 to 2025-08-20.
- Cases with no `triage_at` most likely come from the Slack Re-open button, which sets the status without running the transition flow. I couldn't confirm which cases are affected because the logs have no case IDs.
- The job now counts from `created_at` when `triage_at` is missing. Two tests cover this. The Re-open button path still needs a decision from you.

**Deduplication and snooze regressions (same batch)**

- **Dedup windows:** `917a0b7b` (2025-08-14) switched the per-filter window from minutes to seconds, but the UI still sends minutes. A 30-minute window became 30 seconds. Fixed by converting minutes to seconds in code, so existing filters work unchanged. Regression test added.
- **Snooze:** `086dc910` (2025-08-07) changed the expired-filter check from `continue` to `break`, so a valid snooze filter after an expired one was never checked. Restored `continue`. Regression test added.
- The canary change (`a348bbd2`, 2025-05-29) is still in place and correct. Canary instances are excluded from dedup. Only the three commits above caused regressions.
- Default dedup window is 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Before `7a9fe810` it was hard-coded to 1 hour.

Test results: `python -m pytest tests/signal tests/case` gives 59 passed, 1 skipped. I did not run the full test suite. Everything above is uncommitted. The hashes listed are the commits that introduced the regressions.

```
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
```