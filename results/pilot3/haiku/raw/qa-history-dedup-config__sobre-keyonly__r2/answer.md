The commit that made the window configurable is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). It replaced a hard-coded `timedelta(hours=1)` in `filter_dedup` (`src/dispatch/signal/service.py`) with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defined in `src/dispatch/config.py`.

The new default is 45 minutes, not the old 1 hour, so deployments that don't set the env var will see a behavior change.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (60 minutes)