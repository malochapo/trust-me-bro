The commit is 7a9fe810 (Jordan Lee, 2025-06-19), "feat(signal): make the default deduplication window configurable". It added a `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `src/dispatch/config.py`, with a default of 45 minutes. `filter_dedup` in `src/dispatch/signal/service.py` now reads that setting for signals with no filters. Before the commit, the window was hard-coded as `timedelta(hours=1)`.

The later commit 9dc24f46 only refactored the window computation, so it isn't the one you asked about.

I took "grouping window" to mean this deduplication window, since it is the only default window for filterless signals that I found.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour