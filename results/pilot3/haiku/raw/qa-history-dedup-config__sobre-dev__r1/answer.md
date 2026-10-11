The commit is `7a9fe810`, "feat(signal): make the default deduplication window configurable". It replaced a hard-coded 1-hour window with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting, which defaults to 45 minutes in `src/dispatch/config.py`. The change is in `filter_dedup` in `src/dispatch/signal/service.py`, where `timedelta(hours=1)` became `timedelta(minutes=SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES)`.

The date is the author date from git (2025-06-19). The previous value was 1 hour (60 minutes).

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour