**Weekly Monday reminders (case close and stable)**
- The weekday check used `isoweekday()`, which returns 1 for Monday, and compared it with `calendar.MONDAY`, which is 0. Monday never matched, so no weekly reminders went out from the Monday 2025-08-18 run. Introduced by `c509d45e`, shipped in `main-81d8ae42` on 2025-08-13. The 2025-08-11 run still sent reminders.
- Fixed to `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py`.
- The deploy link is inferred from the tag and commit order. I did not check the image contents.

**Evening TypeError in the close reminder job**
- `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is `None` for cases reopened straight into triage from the Slack reopen button (`reopen_button_click`), which skips the flow that stamps it.
- The job now counts from `triage_at`, falling back to `created_at`. Regression tests: `tests/case/test_case_scheduled.py`.
- Not confirmed: the logs have no case IDs, so I matched the error to this code path rather than to specific cases.
- Open: the reopen handler still bypasses the transition flow. The stable reminder still skips cases with no `stable_at`.

**Signal deduplication and snoozing (same batch of changes)**
- Per-filter dedup windows: `917a0b7b` changed the unit from minutes to seconds, so a window of 30 (set in the UI as minutes) became 30 seconds. Fixed to read the window as minutes again, with the model comment and default updated. Regression tests: `tests/signal/test_signal_service.py`.
- Canary signals: `a348bbd2` stopped canary signals from being deduplicated. No change needed.
- Snoozing: `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze after an expired one was never applied. Fixed back to `continue`. Regression test: `tests/signal/test_signal_service.py`.
- Full suite: 368 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`, and also fail on a clean HEAD checkout. I did not investigate them.
- Open: the API schema still defaults `window` to 600, which now means 10 hours. Decide whether that should be 60.

**Status**
- Nothing is committed. The working tree has the changes in `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py`, and `tests/signal/test_signal_service.py`, plus the new `tests/case/test_case_scheduled.py`.

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