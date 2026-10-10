The window is 45 minutes by default. The `filter_signal` docstring in `src/dispatch/signal/service.py` still says "1-hour window", but that is out of date. The code in `filter_dedup` is what applies.

When a signal has no filters, `filter_dedup` looks for an earlier, non-canary instance of the same signal from the last `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` minutes that already belongs to a case. If it finds one, it attaches the new instance to that case and marks it as deduplicated.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is read as an integer number of minutes through the config loader. The setting is defined at `src/dispatch/config.py:95`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py