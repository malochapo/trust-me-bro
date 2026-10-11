The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". The window it changed is the deduplication window for signals that have no filter, which is the grouping window you described. Before the commit, `filter_dedup` in `src/dispatch/signal/service.py` hard-coded it as `timedelta(hours=1)`. The commit replaced that with the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `src/dispatch/config.py`, which defaults to 45 minutes. Commit a098a3a2 (#3329) is where the 1-hour default originally came from.

I didn't check whether any other commit touched this window.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour