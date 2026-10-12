**Cause:** commit `917a0b7b` ("refactor(signal): share the lookback window computation"). Before it, `filter_dedup` used `timedelta(minutes=f.window)`. The refactor moved to a `_window_start(seconds)` helper and passed `f.window` straight in, with a comment saying the value is in seconds. But the UI's "Window (minutes)" picker (5–30) stores minutes, and existing rows hold minutes. So a window of 30 became 30 seconds, and two instances ten minutes apart no longer matched.

**Fix** (`src/dispatch/signal/service.py`): `filter_dedup` now calls `_window_start(f.window * 60)`, so the stored value is read as minutes again. No data migration is needed and existing filters work unedited. I also corrected the `SignalFilter.window` column comment and default in `models.py`. The default was `60 * 60` "seconds", and it is now `60` minutes, which is still one hour. That default only applies to newly created rows, so no migration is needed there either.

**Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes`. It uses a `window=30` filter with instances 40 and 10 minutes old, and expects the new instance to dedupe into the 10-minute-old one's case. It fails on the old code and passes now. The full `tests/signal` run gives 33 passed and 1 skipped.

**Related bug, not fixed:** `086dc910` changed `continue` to `break` on an expired snooze filter in `filter_snooze`. One expired snooze filter now stops the loop, so any later snooze filters on that signal are never checked. I left it alone since you didn't ask for it.

I didn't commit anything.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES