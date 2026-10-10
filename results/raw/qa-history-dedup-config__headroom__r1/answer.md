The commit is 7a9fe8103c. It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` in `src/dispatch/signal/service.py` with the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting. That setting is defined in `src/dispatch/config.py` and defaults to 45 minutes.

I took "grouping window" to mean this deduplication window, since it is the only window applied to signals with no filters. I didn't search for other commits that touch it.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour