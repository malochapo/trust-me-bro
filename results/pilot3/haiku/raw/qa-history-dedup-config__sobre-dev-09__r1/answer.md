The commit is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). It replaced a hard-coded `timedelta(hours=1)` in `filter_dedup` (`src/dispatch/signal/service.py`) with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defined in `src/dispatch/config.py` with a default of 45. The previous window was 1 hour, which is 60 minutes.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (60 minutes)