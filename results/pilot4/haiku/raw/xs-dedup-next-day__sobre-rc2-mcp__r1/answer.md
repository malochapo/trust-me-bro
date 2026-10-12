The bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the deduplication lookback to read `SignalFilter.window` as seconds, but the UI and existing rows store minutes. So a window of 30 became 30 seconds, and two instances ten minutes apart never grouped. I don't have yesterday's list, so I rebuilt the candidates from git history since 2025-05-22 by searching the signal code for dedup, snooze, window and canary changes.

**Fix**
- `src/dispatch/signal/service.py`: the lookback now converts minutes to seconds (`_window_start(f.window * 60)`), so existing filters work without edits.
- `src/dispatch/signal/models.py`: the column comment and default now say minutes (`default=60`, still one hour). No migration is needed because the stored values were already minutes.
- `filter_signal`'s docstring said the default window was one hour; it now names the setting.

**Tests**
- Added `test_filter_actions_deduplicate_window_in_minutes`: a window-30 filter groups two instances ten minutes apart. It fails on the buggy line and passes with the fix.
- Added `test_filter_actions_deduplicate_window_expired_in_minutes`: an instance 40 minutes old is outside a 30-minute window and is not grouped.
- `python -m pytest tests/signal`: 34 passed, 1 skipped. I did not run the full suite. Ruff isn't installed here, so I didn't lint.

**Things I left alone**
- `SignalFilterBase.window` in `models.py` still defaults to `600`, which is now 600 minutes for API-created filters that omit a window. It predates the bug and matches the stored unit, but you may want it lower.
- The canary behaviour is unchanged. Canary instances are excluded from deduplication by `a348bbd2` ("fix(signal): don't dedup on canary signals", 2025-05-29), which is the commit for the canary line below.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES