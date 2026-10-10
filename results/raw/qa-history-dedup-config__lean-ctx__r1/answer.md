The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". Before it, `filter_dedup` in `src/dispatch/signal/service.py` hard-coded the window for signals without filters as `timedelta(hours=1)`. The commit replaced that with a `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `src/dispatch/config.py`, which defaults to 45 minutes.

I took "grouping window" to mean this deduplication window. The later commit 9dc24f46 only refactors the window computation, so it isn't the one you want.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour