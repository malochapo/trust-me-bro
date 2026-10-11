The commit that made the window configurable is `7a9fe810`, "feat(signal): make the default deduplication window configurable". It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` (`src/dispatch/signal/service.py`) with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is defined in `src/dispatch/config.py`.

That commit also changed the default: the env var falls back to 45 minutes, so the effective default moved from 60 to 45 minutes. The `filter_signal` docstring still says "1-hour window", which is now out of date. The later commit `9dc24f46` only refactored the lookback computation.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (60 minutes)