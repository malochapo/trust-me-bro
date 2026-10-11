## Recap

Two regressions came out of the signal refactors from August 2025. Both are fixed in the working tree and not yet committed.

- **Dedup windows:** `917a0b7b` switched a filter's `window` from minutes to seconds, but the UI field is "Window (minutes)". A filter set to 30 therefore deduped over 30 seconds instead of 30 minutes. `filter_dedup` now applies `f.window * 60` seconds. The `SignalFilter.window` column default (3600 to 60) and the schema default (600 to 10) now read as minutes. Existing filters work without being edited.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`. An expired filter listed before a valid one stopped the loop, so the valid snooze was never applied. It is `continue` again.
- **Canary signals:** `a348bbd2` made `filter_dedup` skip canary instances and exclude canary instances as dedup matches. It did not change any window.
- **Default window:** `7a9fe810` replaced the hard-coded 1 hour for signals without filters with a setting. The default is 45 minutes. The `filter_signal` docstring still says "1-hour", which is out of date.
- **Tests:** I added two regression tests in `tests/signal/test_signal_service.py`. Both fail without the fixes. The file's result is 16 passed, 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES