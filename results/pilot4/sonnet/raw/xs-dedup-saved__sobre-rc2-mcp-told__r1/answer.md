Commit 917a0b7b ("refactor(signal): share the lookback window computation", 2025-08-14) caused it. It added a `_window_start(seconds)` helper and passed `f.window` to it as seconds. The UI window and the existing stored values are in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart therefore never grouped.

**Fix**
- **`src/dispatch/signal/service.py`:** `_window_start` now takes minutes. The default-window call no longer multiplies by 60, and the misleading "stored in seconds" comment is corrected. Existing filters work without editing.
- **`src/dispatch/signal/models.py`:** I changed the `SignalFilter.window` column default from 3600 to 60 and fixed its comment. Without this, a new filter that omits the window would have meant 3600 minutes. I did not touch the Pydantic default of 600 on `SignalFilterBase`, and there is no migration.

**Regression test**
- `test_filter_actions_deduplicate_window_is_in_minutes` is in `tests/signal/test_signal_service.py`. It creates an instance that opened a case 10 minutes ago, then checks that a new instance with a 30-minute window is deduplicated into that case.
- It fails without the fix. With the fix, `python -m pytest tests/signal` gives 33 passed and 1 skipped.

I did not run the rest of the suite.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES