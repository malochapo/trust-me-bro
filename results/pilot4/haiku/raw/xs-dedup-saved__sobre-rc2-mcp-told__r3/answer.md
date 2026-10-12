The deduplication bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how `SignalFilter.window` is read from minutes to seconds. The UI still stores minutes ("Window (minutes)", values 5–30), so a filter set to 30 was looking back 30 seconds. The two GuardDuty instances ten minutes apart fell outside that window and each opened a case.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter path passes `f.window` directly, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Existing filters keep their stored values and are read as minutes, so nothing needs editing.
- `src/dispatch/signal/models.py`: the column default is now `60` (minutes) instead of `60 * 60`, and the schema default is `60` instead of `600`. The schema default changed value, so API clients that omit `window` will now get one hour instead of 600 minutes. I chose 60 to match the one-hour intent in the comment; say if you want a different default.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_minutes`. It creates an instance ten minutes old, a filter with `window=30`, and asserts the new instance joins that case. It fails on the old code and passes with the fix.

`python -m pytest tests/signal` passes (33 passed, 1 skipped).

**Scope**: I only ran the signal tests. I did not run the full suite.

**Canary commit**: `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals"). It was not part of this bug and is unchanged.

**Default window**: signals with no filters use 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES