The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` with a new setting, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45. The grouping window for signals without a filter is the deduplication window.

I found it by searching the signal code's history for "window". The later commit 9dc24f46 only refactored the lookback computation, so it isn't the one that made the window configurable.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour