The commit is 7a9fe810 (Jordan Lee, 2025-06-19), "feat(signal): make the default deduplication window configurable". Before it, `filter_dedup` in `src/dispatch/signal/service.py` used a hard-coded `timedelta(hours=1)` for signals with no filters. The commit replaced that with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, which defaults to 45 minutes.

The `filter_signal` docstring still says "1-hour window". I didn't check whether anything else touches it.

I confirmed this from the commit's diff. I didn't run the code.

COMMIT: 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651
AUTHOR: Jordan Lee
DATE: 2025-06-19
PREVIOUS_VALUE: 1 hour