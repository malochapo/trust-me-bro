The window is 45 minutes. When a signal has no filters, `filter_dedup` in `signal/service.py` looks for an earlier non-canary instance of the same signal created within that window that already has a case. If it finds one, the new instance is attached to that case and marked as deduplicated.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is an integer number of minutes, and 45 is the default. It is read through the config helper in `src/dispatch/config.py`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py