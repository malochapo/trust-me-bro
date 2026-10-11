The default window is 45 minutes. When a signal has no filters, `filter_dedup` in `src/dispatch/signal/service.py` looks for an earlier instance of the same signal created within that window. The earlier instance must already be attached to a case, and canary instances are ignored. If one is found, the new instance is attached to that case and marked as deduplicated.

An operator changes the window by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. It is read through the config loader, so it can also come from the `.env` file.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py