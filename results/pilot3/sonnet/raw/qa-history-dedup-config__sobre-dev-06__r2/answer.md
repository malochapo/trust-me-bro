The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". The repo calls this the "deduplication window" rather than the "grouping window". The commit message says the window applied to signals without a deduplication filter was hard-coded. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. Before the commit, `filter_dedup` in `src/dispatch/signal/service.py` used `timedelta(hours=1)`.

The hard-coded 1-hour window was added earlier, in a098a3a2 (Will Sheldon, 2023-05-01). A later refactor, 9dc24f46, only shares the lookback computation.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour