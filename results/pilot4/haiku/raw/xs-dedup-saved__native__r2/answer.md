The regression came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the filter window from minutes to seconds, so a stored 30 became 30 seconds. The two instances ten minutes apart fell outside that window and opened separate cases.

**Evidence:** The UI labels the field "Window (minutes)" with options 5–30. Commit `9c523348` (2023) made the code use minutes to match. `917a0b7b` switched it back to seconds without touching the UI. The model comment and column default still said seconds, which was stale.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path and the no-filter default both pass minutes, so existing stored filters (e.g. 30) work without edits.
- `src/dispatch/signal/service.py`: the `filter_signal` docstring now names `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` instead of a fixed 1-hour window.
- `src/dispatch/signal/models.py`: the column default is 60 minutes (1 hour), with the comment corrected. The old default of 3600 would have meant 60 hours under minutes. This only applies to rows inserted without a window, so existing rows are unaffected.
- `tests/signal/test_signal_service.py`: two regression tests. One checks that a 30-minute window groups an instance from 10 minutes earlier. The other checks that a 5-minute window does not. The first fails on the old code and passes now.

**Verification:** `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite. Nothing is committed.

**Not changed, for you to decide**
- `086dc910` changed `continue` to `break` for expired snoozes in `filter_snooze`. Once one snooze has expired, later snooze filters on the same signal are skipped. It is a snooze bug, not the window bug, so I left it alone.
- The API schema default for `window` is still 600. That now means 600 minutes (10 hours) when the field is omitted. This matches the behavior before the regression, but it may be worth reviewing.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES