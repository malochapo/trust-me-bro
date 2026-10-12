**Culprit:** `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). It changed the per-filter window from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI and the stored data are in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, which is why they opened two cases.

**Fix:**
- In `src/dispatch/signal/service.py`, `filter_dedup` now uses `_window_start(f.window * 60)`. Windows are minutes again, so existing filters work without edits and no migration is needed.
- I corrected the `filter_signal` docstring, which still said "1-hour window". I also fixed the `SignalFilter.window` comment in `models.py`, which said seconds.
- I left the column default (3600) and the pydantic default (600) as they were. They look odd as minutes, but changing them would alter behavior for new filters you didn't ask me to touch.

**Test:** I added `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It has an instance from 10 minutes ago, a new one, and a filter with window=30, and it expects the new one to be deduplicated.
- The test fails without the fix and passes with it.
- `python -m pytest tests/signal` gives 33 passed and 1 skipped.

The canary change is `a348bbd2` (2025-05-29, #6026): canary signals skip dedup, and earlier canary instances are excluded from the dedup queries.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES