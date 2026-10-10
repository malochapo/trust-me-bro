The window is 45 minutes by default. The docstring of `filter_signal` still says "1-hour window", but the code uses the setting's default of 45, so the docstring is out of date.

When a signal has no filters, `filter_dedup` in `signal/service.py` looks for another instance of the same signal created within that window. The instance must already be attached to a case and must not be a canary. If it finds one, the new instance joins that case and is marked as deduplicated.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable, which is read as an integer number of minutes.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py