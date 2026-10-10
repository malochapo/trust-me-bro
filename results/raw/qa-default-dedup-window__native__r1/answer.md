The window is 45 minutes by default. The `filter_signal` docstring in `signal/service.py` still says "1-hour window", but the code uses the setting below.

When a signal has no filters, `filter_dedup` in `signal/service.py` looks for another instance of the same signal created within the window that already has a case. It skips canary signals. If it finds one, the new instance is grouped into that case.

An operator changes the window with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable. It is read as an integer number of minutes through the config loader.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py