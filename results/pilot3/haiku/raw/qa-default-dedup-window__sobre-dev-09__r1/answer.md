When a signal has no filters, a new instance is grouped into a recent case if an earlier instance of the same signal, with a case attached, was created within the last **45 minutes**. The check is in `filter_dedup` in `src/dispatch/signal/service.py` (around lines 801–820), which takes the most recent matching instance's case. Canary instances are excluded.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is read as an integer number of minutes and defaults to 45.

Two comments in the code say 1 hour: the docstring of `filter_signal` in `service.py` and the `SignalFilter.window` comment in `models.py`. Those describe the old default, and the code uses the 45-minute config value. The 1-hour `window` on `SignalFilter` applies only to signals that do have filters.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py