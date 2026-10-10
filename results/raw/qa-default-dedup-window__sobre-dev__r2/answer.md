The window is 45 minutes. When a signal has no filters, `filter_dedup` in `signal/service.py` looks for the most recent non-canary instance of the same signal that already has a case. It only considers instances created within that window. If it finds one, the new instance is attached to that case and marked as deduplicated.

The `filter_signal` docstring still says "1-hour window", but the code uses the configured 45-minute default.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. It is read through the config helper, with 45 as the default. The setting is defined in `src/dispatch/config.py`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py