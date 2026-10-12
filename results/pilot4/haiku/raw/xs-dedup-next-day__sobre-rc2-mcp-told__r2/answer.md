The window bug came from `917a0b7b` (refactor(signal): share the lookback window computation). It is fixed, and the signal test suite passes (34 passed, 1 skipped).

**Cause:** The UI labels the window "Window (minutes)" with options 5–30, and existing rows store that number as minutes. Before `917a0b7b`, `filter_dedup` converted it with `timedelta(minutes=f.window)`. That commit passed the raw value into `_window_start`, which takes seconds. A window of 30 therefore became 30 seconds, so an instance ten minutes earlier fell outside it and opened a second case.

**Fix** (`src/dispatch/signal/service.py`):
- The lookback now uses `_window_start(f.window * 60)`. Existing filters keep their stored values and need no edits.
- The `filter_signal` docstring said "1-hour window" for the default. It now names `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Related change** (`src/dispatch/signal/models.py`): The `SignalFilter.window` column default was 3600 with a "seconds" comment, and the Pydantic schema default was 600. Both would mean hours if read as minutes. I changed them to 60 minutes and updated the comment. Existing rows are unaffected. This was not strictly required by the bug, so say if you'd rather keep it separate.

**Regression tests** (`tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_in_minutes`: window 30, previous instance ten minutes old, expects deduplication into the existing case. I confirmed it fails when the `* 60` is removed.
- `test_filter_actions_deduplicate_window_excludes_older_instances`: window 30, previous instance forty minutes old, expects no deduplication.

**Other commits:** The canary change is `a348bbd2` (fix(signal): don't dedup on canary signals, #6026). `7a9fe810` made the default window configurable and did not cause this bug.

**Default window:** Signals without a filter use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes (`src/dispatch/config.py`).

**Caveats:**
- I had no record of yesterday's list in this session, so I took the commits from `git log --since=2025-05-22` and traced the window code through them.
- `ruff` is not installed here, so lint was not run.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES