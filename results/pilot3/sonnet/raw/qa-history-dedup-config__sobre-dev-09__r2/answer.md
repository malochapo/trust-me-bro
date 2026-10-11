Commit 7a9fe810 replaced the hard-coded `timedelta(hours=1)` in `src/dispatch/signal/service.py` with a new setting, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. The setting is defined in `src/dispatch/config.py` with a default of 45 minutes. I found it by searching history for when that setting name first appeared, and I read the diff to confirm the old value.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour