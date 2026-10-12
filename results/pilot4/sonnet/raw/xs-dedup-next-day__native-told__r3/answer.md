The test now fails without the fix and passes with it.

Deduplication windows broke in **917a0b7b** ("share the lookback window computation", 2025-08-14). It changed the filter lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. It did this on the wrong assumption that `window` is stored in seconds. The UI offers the window in minutes (5 to 30), and existing rows hold minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases.

The other commits you listed are not the cause:
- 7a9fe810 made the default window configurable.
- 086dc910 simplified the snooze checks.
- a348bbd2 made canary signals skip deduplication.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Filters use `f.window` as minutes, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. Existing filters work without edits. I also corrected the `filter_signal` docstring, which still said "1-hour window".
- `src/dispatch/signal/models.py`: the column default and comment said 3600 seconds, which would now read as 3600 minutes. I changed the default to 60 minutes for new filters.

**Test**
`test_filter_actions_deduplicate_window_is_in_minutes` uses a 30-minute filter and an earlier instance 10 minutes old that has a case. It asserts the new instance is deduplicated into that case. It fails on the old code and passes now; the rest of `tests/signal/test_signal_service.py` passes too (15 passed, 1 skipped).

The existing deduplication tests append filters to `signal.filters` without adding them to the session first. In my first attempt the filter never attached, so the test used the default 45-minute path and passed on the old code too. I added `session.add(signal_filter)` in the new test. I did not touch the other tests, so they may still be exercising the default path instead of their filters.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES