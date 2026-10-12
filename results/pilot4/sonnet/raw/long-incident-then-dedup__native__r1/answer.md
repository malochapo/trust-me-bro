## Recap

**1. Weekly Monday close reminders stopped (case reminders)**
- **Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday is 1 and Sunday is 7) with `calendar.MONDAY` (which is 0). The check was never true, so the weekly triage and stable reminders stopped. The daily triage reminders don't use that check, so they kept arriving.
- **Introduced by:** `c509d45e`. It shipped in image `main-81d8ae42` on 2025-08-13 at about 16:40 UTC. That was a Wednesday, so the first Monday affected was 2025-08-18.
- **Fix:** the check now uses `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`.

**2. Evening `TypeError` in the case close reminder job**
- **Cause:** the job computes `datetime.utcnow() - case.triage_at`, but `triage_at` is only set by the status-transition flow into triage. Cases created directly in triage, or that reached it by another transition, have `triage_at` as None. The per-case `try/except` logged the error each evening, and those cases never got a reminder.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. Tests cover a 10-day-old case with no `triage_at` (reminder sent) and a 2-day-old one (not sent).
- **Left alone:** `case_stable_reminder` still skips cases with no `stable_at`.

**3. Signal snooze and deduplication changes since 2025-05-22**
- `a348bbd2` made canary signal instances skip deduplication and stopped them from matching as duplicates.
- `7a9fe810` made the default dedup window configurable. It was 1 hour and is now 45 minutes unless the setting is overridden.
- `086dc910` changed `continue` to `break` for an expired snooze filter. A valid snooze filter listed after an expired one was then never checked. I fixed it by restoring `continue` and added a regression test.
- `917a0b7b` made the filter window count seconds, while the UI field "Window (minutes)" still sends minutes. A window of 30 became 30 seconds, which is why the two GuardDuty instances ten minutes apart opened two cases. I fixed it with `f.window * 60`, so existing filters work without being edited, and added a regression test.
- `4474af25` only added log lines.

Nothing is committed. All three fixes need to be deployed.

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