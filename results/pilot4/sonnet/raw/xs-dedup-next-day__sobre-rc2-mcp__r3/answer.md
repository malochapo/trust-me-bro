The commit that broke it is 917a0b7b ("refactor(signal): share the lookback window computation"). It's fixed, and the signal tests pass (33 passed, 1 skipped).

**Cause.** The deduplication filter used to compute its lookback with `timedelta(minutes=f.window)`. The UI offers 5, 10, 15, 20 and 30 and stores them as minutes. 917a0b7b replaced that with a shared `_window_start(seconds)` helper and added a comment saying `SignalFilter.window` is stored in seconds. That comment was wrong, so a window of 30 became 30 seconds. Instances ten minutes apart no longer matched and each opened its own case. The same commit also changed the default-window path to `* 60` so it stayed in minutes.

**Fix.**
- `_window_start` in `src/dispatch/signal/service.py` now takes minutes, and the default-window call no longer multiplies by 60.
- The wrong comments in `service.py` and in the `window` column comment in `src/dispatch/signal/models.py` are corrected.
- No data migration is needed, because the stored values were always minutes.

**Regression test.** `test_filter_actions_deduplicate_window_is_in_minutes` uses a filter with window 30 and an earlier instance 10 minutes old. It fails without the fix and passes with it. The existing dedup tests didn't catch this: in the one I inspected, the filter never attached to the signal, so the default-window branch ran instead.

**Left alone.** The `window` column default is `60 * 60` and the pydantic default is 600. Read as minutes, those are 60 hours and 10 hours. They only affect filters created without an explicit window; I didn't change them.

The other commits you listed are not the cause. The default-window setting (7a9fe810) and the canary-signal handling (a348bbd2) don't touch filter windows. 086dc910 changes the snooze checks.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES