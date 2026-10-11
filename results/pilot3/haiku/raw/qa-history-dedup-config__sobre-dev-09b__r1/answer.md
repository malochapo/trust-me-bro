The commit is `7a9fe810` ("feat(signal): make the default deduplication window configurable"). It moved the hard-coded window into `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, and `filter_dedup` in `src/dispatch/signal/service.py` now reads it.

Before this commit the window was `timedelta(hours=1)`. The new env var defaults to 45 minutes, so an unset deployment now dedups over a 45-minute window instead of 1 hour. The commit message doesn't mention that change, so you may want to confirm it was intended.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour (hard-coded as `timedelta(hours=1)`)