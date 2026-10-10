The commit is 7a9fe810, "feat(signal): make the default deduplication window configurable". It replaced the hard-coded `timedelta(hours=1)` in `filter_dedup` with a setting read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 in `config.py`. The window used to be 1 hour.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour