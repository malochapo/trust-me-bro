The commit is 7a9fe810 ("feat(signal): make the default deduplication window configurable"). The default window for signals with no filter was `timedelta(hours=1)`, hard-coded in `filter_dedup`. The commit replaced it with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.

I read "grouping window" as the deduplication window, since that is the one this commit changed.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour