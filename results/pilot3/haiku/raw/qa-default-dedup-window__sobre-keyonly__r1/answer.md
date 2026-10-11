When a signal has no filters, new instances are grouped into an existing case if a prior instance of that signal was created within the last **45 minutes** and is already attached to a case. The lookback is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read from `src/dispatch/config.py` via `config(...)` with `default=45`. The grouping logic is in `filter_dedup` in `src/dispatch/signal/service.py`, which uses that value as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable (an integer, in minutes) on the Dispatch deployment and restarting it. I did not change any code.

The docstring of `filter_signal` in `src/dispatch/signal/service.py` says "1-hour window", which is stale. The code default is 45 minutes.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py