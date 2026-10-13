Recap of today's work. Nothing is committed.

**1. Weekly close and stable reminders (Mondays)**
Reminders stopped after the 2025-08-13 deploy. `_is_reminder_day()` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so it never matched. Commit `c509d45e` introduced the comparison. It was deployed as `main-81d8ae42` on 2025-08-13 at 16:40Z. The first Monday with no reminders was 2025-08-18. The fix uses `date.today().weekday()`, and `tests/case/test_case_scheduled.py` covers each weekday. The test fails on the old code.

**2. Evening TypeError in the case close reminder job**
Some triage cases never set `triage_at`. Only `case_triage_status_flow` sets it, and some Slack handlers set `CaseStatus.triage` directly, skipping that flow. `datetime.utcnow() - None` then raised a TypeError on every run. The job now counts from `triage_at or created_at`, so those cases still get their weekly reminder. Three tests cover it.

**3. "GuardDuty: Unauthorized API call" dedup windows**
Commit `917a0b7b` (2025-08-14) changed the custom dedup window from minutes to seconds. A 30-minute window became 30 seconds, so two instances ten minutes apart opened two cases. The window is minutes again. The defaults in the model and schema keep their meanings (1 hour and 10 minutes). Existing filters need no edits. `tests/signal/test_signal_dedup_window.py` covers this.

**4. "Okta: Impossible travel" snoozes**
Commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`. The loop stopped at the expired filter, so a later valid snooze filter was never checked. The expired branch now uses `continue`. `tests/signal/test_signal_snooze.py` covers this.

**Results:** `python -m pytest`: 372 passed, 4 skipped, 8 failed. The 8 failures are AI, database, and entity tests that also fail on the base commit. I have not looked into them.

**Open items:**
- `case_stable_reminder` still skips cases with no `stable_at` and has no fallback. You did not ask for one.
- The Slack handlers that set triage directly still skip the transition flow.
- The docstring for `filter_signal` still says the default window is 1 hour.
- `086dc910` also removed the warnings for filters with no mode or action. Those are now skipped silently.

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