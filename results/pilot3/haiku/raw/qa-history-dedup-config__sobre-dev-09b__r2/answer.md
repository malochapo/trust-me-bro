The commit that made the window configurable is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). It adds `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` to `src/dispatch/config.py` with a default of 45, and replaces the hard-coded `timedelta(hours=1)` in `src/dispatch/signal/service.py`.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded as `timedelta(hours=1)`, i.e. 60 minutes)