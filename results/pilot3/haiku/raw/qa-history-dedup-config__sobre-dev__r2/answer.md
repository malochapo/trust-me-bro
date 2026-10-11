The commit that made the window configurable is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). It is reachable from `main`.

It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` (`src/dispatch/signal/service.py`) with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read from the environment in `src/dispatch/config.py`. That variable defaults to 45, so the effective default changed from 1 hour to 45 minutes. The hard-coded 1-hour value came from `a098a3a2`.

Two things you may want to check:
- The docstring of `filter_signal` still says "1-hour window", which is now stale.
- The commit message says the value is "read from" the env var, but the default is 45 minutes, not the old 60. Anyone relying on the 1-hour behaviour needs to set `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES=60`.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded as timedelta(hours=1))