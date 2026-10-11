The default window is 45 minutes. The docstring of the function in `src/dispatch/signal/service.py` (around line 873) says "1-hour window", but that text is out of date. The code uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, and the setting defaults to 45.

When a signal has no filters, a new instance is attached to the most recent non-canary instance of the same signal that has a case. That instance must have been created within the window, and the new instance is marked as `deduplicate`.

An operator can change the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable (an integer number of minutes). It is read through `config(...)` in `src/dispatch/config.py`.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py