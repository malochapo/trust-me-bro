When a signal definition has no filters, a new instance is grouped into an existing case if a matching instance with a case was created within the last **45 minutes**. The matching instance is the most recent one for the same signal, and canary instances are ignored. The code is in `filter_dedup` in `src/dispatch/signal/service.py` (around lines 800–820).

An operator changes this with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read through `config()` (so a `.env` file or the process environment both work). It is an integer number of minutes. The default of 45 is set in `src/dispatch/config.py`.

The docstring of `filter_signal` in `service.py` says "1-hour window", which contradicts the 45-minute default in code. The code is what runs, so I've reported 45 minutes. The docstring is stale and should be corrected.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py