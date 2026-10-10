Commit 7a9fe810 made the window configurable. It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` with the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting, which defaults to 45 minutes today. The `filter_signal` docstring still says "1-hour window", so it is out of date.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour