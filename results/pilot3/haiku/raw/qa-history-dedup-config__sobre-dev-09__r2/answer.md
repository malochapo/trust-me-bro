The commit that made the window configurable is `7a9fe810`, "feat(signal): make the default deduplication window configurable". It replaced a hard-coded `timedelta(hours=1)` in `filter_dedup` (`src/dispatch/signal/service.py`) with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defined in `src/dispatch/config.py`. The new environment-variable default is 45 minutes, so the effective default changed from 60 to 45 minutes. The `filter_signal` docstring still says "1-hour window", which is now stale.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (60 minutes, hard-coded)