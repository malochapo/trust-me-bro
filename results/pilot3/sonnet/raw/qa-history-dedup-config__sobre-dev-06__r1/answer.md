The commit is 7a9fe810 by Jordan Lee, dated 2025-06-19. It made the default deduplication window configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is now set in `src/dispatch/config.py` and read in `filter_dedup` in `src/dispatch/signal/service.py`. The window it replaced was hard-coded as `timedelta(hours=1)`, and the new setting defaults to 45 minutes.

The commit calls this a "deduplication" window, not a "grouping" window. I took it to be the one you meant because it applies to signals that have no filters.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour