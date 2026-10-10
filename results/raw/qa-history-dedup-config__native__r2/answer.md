The commit is 7a9fe810 (Jordan Lee, 2025-06-19), "feat(signal): make the default deduplication window configurable". It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` with a new setting, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. The new setting defaults to 45 minutes, so the default window is now shorter than the old one.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour