The bug came from `917a0b7b`, and the fix is in place: a filter's window is read as minutes again, so existing filters work without edits. The signal test suite passes (34 passed, 1 skipped), including a new regression test that failed before the fix.

I don't have yesterday's list, so I rebuilt the candidates from git history since 2025-05-22. The main ones are `917a0b7b`, `a348bbd2`, `7a9fe810`, and `086dc910`.

**Cause:** `917a0b7b` ("share the lookback window computation", Aug 14) changed `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the stored value as seconds. The UI offers 5–30 labeled "Window (minutes)", so a 30 window became 30 seconds. Two instances ten minutes apart fell outside it and each opened a case. The stale comment saying the column was seconds came from the original 2022 model and was never true for the service code.

**Changes:**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`. I also corrected the `filter_signal` docstring, which said the default window was 1 hour.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column comment now says minutes, and its default changed from 3600 to 60 so it still means 1 hour. No migration is needed, since this is a Python-side default.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes` (30-minute window, instance 10 minutes old, expects dedup) and `test_filter_actions_deduplicate_window_excludes_older_instances` (40 minutes old, expects no dedup).

I did not run the full repository suite, only `tests/signal`.

**Other findings, not fixed:**
- `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for expired snooze filters. An expired snooze filter now stops the loop, so later active snooze filters are never checked. This is a snooze bug and deserves its own fix.
- The Pydantic default `SignalFilterBase.window = 600` is still 600 minutes, which I left alone. That is 10 hours, not the 10 minutes it effectively was while the service read the value as seconds.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES