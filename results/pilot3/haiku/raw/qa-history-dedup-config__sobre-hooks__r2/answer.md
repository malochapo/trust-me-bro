The commit that made the window configurable is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). Before it, the window for signals without a filter was hard-coded as `timedelta(hours=1)` in `filter_dedup` in `src/dispatch/signal/service.py`. The commit reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from config instead, with a default of 45 minutes. The 1-hour value was introduced by `a098a3a2`, so 1 hour is the value in effect right before this commit.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded as `timedelta(hours=1)`)