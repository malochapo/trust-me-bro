The commit that made the window configurable is `7a9fe810`, "feat(signal): make the default deduplication window configurable."

It replaced `timedelta(hours=1)` in `filter_dedup` with a value read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. That setting is defined in `src/dispatch/config.py` with a default of 45 minutes. So the new default is 45 minutes, not the previous 1 hour, which is a behavior change for deployments that don't set the variable.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded as timedelta(hours=1))