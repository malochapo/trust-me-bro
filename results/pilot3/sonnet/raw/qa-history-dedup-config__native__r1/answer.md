Commit 7a9fe810 replaced the hard-coded default deduplication window with a setting, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Before it, `filter_dedup` in `src/dispatch/signal/service.py` used `timedelta(hours=1)` for signals with no filters. The new setting defaults to 45 minutes.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour