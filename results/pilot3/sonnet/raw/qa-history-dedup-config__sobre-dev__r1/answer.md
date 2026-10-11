The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". Before it, `filter_dedup` in `src/dispatch/signal/service.py` hard-coded `timedelta(hours=1)` for signals with no filters. The commit replaced that with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting, which defaults to 45 minutes.

The commit date is the author date, 2025-06-19.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour