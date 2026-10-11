## Recap

Two regressions came from refactors made in August 2025. Both are fixed in the working tree and not yet committed.

- **Dedup windows:** `917a0b7b` made `SignalFilter.window` be read as seconds. The UI offers 5–30 and stores them as minutes, so a 30-minute window became 30 seconds and related instances opened separate cases. `_window_start` in `src/dispatch/signal/service.py` now takes minutes. The column and pydantic defaults in `models.py` were changed to 60 and 10 so they still mean 1 hour and 10 minutes. No migration is needed for rows saved through the UI. Rows that were never set through the UI and still hold the old default values (3600 or 600) would now be read as minutes and become very long windows, so check for those before release.
- **Snooze:** `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed first then stopped the loop, so a valid filter after it never applied. It is back to `continue`.
- **Canary:** `a348bbd2` made canary instances skip deduplication and excluded existing canary instances from dedup matching.
- **Default window:** `7a9fe810` made the window for signals without filters configurable. It changed from a fixed 1 hour to 45 minutes by default.
- **Tests:** each regression has a test that fails without its fix and passes with it. `tests/signal` shows 34 passed and 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES