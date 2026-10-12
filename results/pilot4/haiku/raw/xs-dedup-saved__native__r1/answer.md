The bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed custom deduplication windows from minutes to seconds, so a window of 30 grouped only 30 seconds of instances. Your two instances ten minutes apart fall outside that, so they opened two cases.

**The root cause**

- Since 2023 (`9c523348`), the backend read `SignalFilter.window` as minutes, which matches the dialog's "Window (minutes)" label and its 5/10/15/20/30 options.
- `917a0b7b` replaced `timedelta(minutes=f.window)` with a seconds-based helper and never changed the UI or the stored values, so existing filters silently shrank.

**The fix**

- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The custom-filter path and the default path both use it in minutes, and the stale "stored in seconds" comment and "1-hour" docstring are corrected.
- `src/dispatch/signal/models.py`: the model default is now 60 (one hour, as its comment already said), and the API schema default is now 10 minutes. The old values, 3600 and 600, were seconds-era numbers that would have become 2.5 days and 10 hours under minutes. This changes what new filters get if they omit `window`. Existing stored values are untouched, so existing filters need no edits or migration.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_in_minutes`, with a 30-minute window. An instance 10 minutes old must be deduplicated, and one 40 minutes old must not.

**Verification**

- The regression test fails on the buggy `service.py` (the 10-minute case) and passes with the fix.
- `python -m pytest tests/signal`: 34 passed, 1 skipped.

**Caveat**

A filter created through the API after `917a0b7b` with a seconds value would now be read as minutes. The stored data cannot distinguish those from UI-created filters, so I did not add a migration. If you have such filters, they need a review.

I also updated the memory note, which had listed this mismatch as unverified.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES