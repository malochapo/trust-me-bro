Commit 7a9fe810 replaced the hard-coded default dedup window (`timedelta(hours=1)`) in `filter_dedup` with a new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting. The new setting defaults to 45 minutes.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour