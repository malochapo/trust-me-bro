The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". Before it, `filter_dedup` in `src/dispatch/signal/service.py` used `timedelta(hours=1)` for signals with no filters. The commit replaced that with a new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, whose default is 45 minutes.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour