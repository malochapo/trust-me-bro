The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". Before it, the window for signals with no filter was hard-coded as `timedelta(hours=1)` in `filter_dedup` in `src/dispatch/signal/service.py`. The commit replaced that with the setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which has a default of 45 minutes. That setting is defined in `src/dispatch/config.py`.

I didn't look at any other commits that touched this code. A later commit, 9dc24f46, only refactored the lookback computation. The `filter_signal` docstring still says "1-hour window", which is out of date.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour