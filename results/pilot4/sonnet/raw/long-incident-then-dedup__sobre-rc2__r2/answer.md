Here is the recap for the weekly report. Nothing is committed.

**1. Weekly Monday reminders stopped (cases in triage and stable)**
- **Cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The helper compares `date.isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, while `calendar.MONDAY` is 0, so the check was never true and the weekly reminders silently stopped. The daily triage reminders don't use this check, which is why they kept arriving.
- **Deploy:** the commit reached production in the 2025-08-13 rollout, image `registry.example.com/dispatch:main-81d8ae42`. I confirmed `c509d45e` is an ancestor of that commit. The scheduler and web pods ran `main-b05613b5` before it.
- **First missed Monday:** 2025-08-18. Six case close reminders went out on 2025-08-11. On 2025-08-18 the only reminders in the log are the daily triage reminder and an incident reminder, which is a different job.
- **Fix:** `_is_reminder_day()` now uses `weekday()`. The regression test checks Mondays, non-Mondays and the 2025-08-11 and 2025-08-18 cases.

**2. Nightly `TypeError` in the case close reminder job**
- **Cause:** `case_close_reminder` computed `utcnow() - case.triage_at`, but `triage_at` is NULL for cases that never went through `case_triage_status_flow`. Those cases raised `TypeError`, the per-case `except` logged it, and the case was skipped, so they never got a reminder. The error appears every evening in the log.
- **Fix:** the job now counts from `triage_at`, or from `created_at` when `triage_at` is missing. Four test cases cover the fallback.
- **Stable job:** `case_stable_reminder` already skips cases with no `stable_at`. The log shows its own `TypeError` stopped after 2025-08-12, so the guard went out with the 2025-08-13 deploy. I did not give it the `created_at` fallback.

**3. Signal deduplication and snoozing (same batch of changes)**
- **Dedup windows:** commit `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds, so a UI value of 30 became 30 seconds. I restored minutes and fixed the misleading column comment and default. The regression test uses window 30 with instances 10 and 40 minutes old.
- **Snoozing:** commit `086dc910` (2025-08-07) turned `continue` into `break` for an expired snooze filter. An expired filter listed first stopped the loop, so a valid filter after it was never checked. I restored `continue`, and a regression test covers it.
- **Canary signals:** commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated. It skips dedup for canary instances and ignores earlier canary instances when matching.
- **Default window:** signals with no filters group instances within 45 minutes. This is configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It was hard-coded at 1 hour before `7a9fe810`, and the `filter_signal` docstring still says 1 hour.
- **Tests:** `tests/signal` gives 34 passed and 1 skipped. The new case-reminder tests pass. The new signal tests fail with the signal fixes reverted.
- **Loose end:** the `SignalFilterCreate.window` pydantic default is still 600, which is 10 hours in minutes.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES