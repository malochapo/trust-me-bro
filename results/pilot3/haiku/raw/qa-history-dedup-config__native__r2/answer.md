The commit that made the window configurable is `7a9fe810`, "feat(signal): make the default deduplication window configurable" (Jun 19, 2025).

Before that commit, `filter_dedup` in `src/dispatch/signal/service.py` used `timedelta(hours=1)` for signals without a filter. The commit moved the value into `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, which reads from the environment with a default of 45 minutes. That's why the previous value was 1 hour (60 minutes). The commit is on `main`.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (60 minutes, hard-coded as `timedelta(hours=1)`)