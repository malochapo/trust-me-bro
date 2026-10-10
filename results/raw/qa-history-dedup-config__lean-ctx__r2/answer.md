The commit is 7a9fe810 ("feat(signal): make the default deduplication window configurable"). Before it, the window for signals without a filter was `timedelta(hours=1)` in `filter_dedup`. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from config, which defaults to 45 minutes.

The commit's own message says "deduplication window". I took that to be the "grouping window" you described.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour