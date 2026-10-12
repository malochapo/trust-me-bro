## Recap of today's work

**Investigation 1: missing Monday reminders for long-running cases**
- Weekly Monday reminders for long-running triage and stable cases stopped after the 2025-08-13 deploy. The daily triage reminders kept arriving.
- The cause is a weekday comparison bug in `_is_reminder_day()`. The check compared `date.isoweekday()`, which is 1-based (Monday = 1), against `calendar.MONDAY`, which is 0-based (Monday = 0). The check was therefore never true.
- The bug came from commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) and shipped in image `main-81d8ae42`.
- Fix: `date.today().weekday() == calendar.MONDAY`. The regression test is in `tests/case/test_case_scheduled.py`. It fails on the old line and passes on the fix.
- First missed Monday: 2025-08-18. The previous Monday, 2025-08-11, ran on the earlier image.

**Investigation 2: close-reminder TypeError every evening**
- The `case_close_reminder` job subtracted `case.triage_at` from the current time. `triage_at` is null for some triage cases, which raised a TypeError each evening.
- The likely path is the catch-all `(_, triage)` transition in `src/dispatch/case/flows.py:766`, which never sets `triage_at`. I did not confirm this from production logs.
- Fix: count from `case.triage_at or case.created_at`, so those cases still get their weekly reminder. The tests are in `tests/case/test_case_scheduled.py`.

**Investigation 3: snooze and dedup regressions (from the signal reports)**
- Deduplication windows: commit `917a0b7b` ("share the lookback window computation", 2025-08-14) changed the filter window from minutes to seconds. The UI labels the field "Window (minutes)", so a window of 30 was read as 30 seconds. Fixed in `src/dispatch/signal/service.py` (`_window_start` takes minutes again), with a regression test in `tests/signal/test_signal_service.py`. No stored data needed changing.
- Snoozing: commit `086dc910` ("simplify snooze filter checks", 2025-08-07) changed `continue` to `break` on expired snooze filters. An expired filter ended the loop, so a valid snooze later in the list was never applied. Fixed back to `continue`, with a regression test.
- Canary signals: commit `a348bbd2` ("don't dedup on canary signals", 2025-05-29) changed how canaries are deduplicated. Canaries are now skipped by both deduplication paths.

**Test status:** `python -m pytest` gives 373 passed, 4 skipped, 8 failed. The 8 failures are in the AI service, one database test, and one entity test. They also fail without these changes and are not related to this work.

**Not committed.** The changes are in the working tree (`scheduled.py`, `signal/service.py`, `signal/models.py`, and two test files). Two defaults still need a decision: the API default `window = 600` and the column default `60 * 60`, which now read as minutes.

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