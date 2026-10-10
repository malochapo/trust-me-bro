The default grouping window is 45 minutes. When a signal has no filters, a new instance is deduplicated into the most recent case from the same signal created within that window. Canary instances are skipped.

An operator changes it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to an integer number of minutes. The logic is in `src/dispatch/signal/service.py`, around line 804.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py