The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". Its message says the window applied to signals without a deduplication filter was hard-coded. The diff replaces `timedelta(hours=1)` in `filter_dedup` with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. That setting is read from the environment and defaults to 45 minutes.

The `filter_signal` docstring still says "1-hour window". It is out of date, because the default is now 45 minutes.

The `git log -S"window"` search I used to find it showed a later commit, 9dc24f46, which only refactored the lookback computation.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour