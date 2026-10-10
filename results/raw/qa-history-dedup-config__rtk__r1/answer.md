Commit 7a9fe810 made the default grouping window configurable. It added a `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `src/dispatch/config.py` and used it in `src/dispatch/signal/service.py`. The new default is 45 minutes. Before the commit, the code hard-coded `timedelta(hours=1)`.

I only have the abbreviated hash from `git log`, so the COMMIT line below is the 8-character form.

COMMIT: 7a9fe810
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour