**Investigation 1: weekly reminders not sent for long-running cases**

Weekly Monday reminders stopped after the 2025-08-13 deploy. The weekday check compared `date.isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0, so the check never matched. Daily triage reminders were not affected. Introduced by `c509d45e` on 2025-08-12 and shipped in image `main-81d8ae42` on 2025-08-13. The fix uses `weekday()` and has regression tests in `tests/case/test_case_scheduled.py`. The first missed Monday is 2025-08-18. That date comes from the deploy date and the code; I did not confirm it against send logs.

The same log stream showed a `TypeError` each evening from the case close reminder job. Cases in triage can have no `triage_at`, and the job subtracted it from the current time. The job now counts from `created_at` when `triage_at` is missing. Cases with `triage_at` behave as before. The root cause of the NULL `triage_at` is still unconfirmed. Two candidates are the Slack reopen path, which sets triage without the transition flow, and legacy rows. The logs have no case IDs and I had no production database access.

**Investigation 2: signal deduplication and snoozing**

- **Deduplication windows:** `917a0b7b` (2025-08-14) changed the filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a 30-minute window became 30 seconds and instances ten minutes apart opened separate cases. The window is minutes again, and existing filters need no edits. Regression tests are in `tests/signal/test_signal_service.py`.
- **Snoozing:** `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter first in the list stopped the check, so a valid filter after it was never applied. Fixed back to `continue`, with a regression test.
- **Canary signals:** `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated and from being used as dedup targets.
- **Default grouping:** signals with no filter are grouped over a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It was a hard-coded 1 hour before `7a9fe810`.

Open items: the model defaults for `SignalFilter.window` (60 × 60 and 600) are still unchanged. Under minute units they mean 60 hours and 10 hours. I did not change them.

Nothing is committed. The uncommitted changes are the weekday and `created_at` fallback fixes in `src/dispatch/case/scheduled.py`, the window-unit and snooze fixes in `src/dispatch/signal/service.py` and `models.py`, and the new tests in `tests/case/test_case_scheduled.py` and `tests/signal/test_signal_service.py`.

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