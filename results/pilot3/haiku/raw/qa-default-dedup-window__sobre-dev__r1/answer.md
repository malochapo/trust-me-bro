The grouping window is 45 minutes. An operator can change it with the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable.

When a signal has no filters, `filter_dedup` in `src/dispatch/signal/service.py` (around lines 803–824) looks for another instance of the same signal created within the last `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` minutes. That instance must already belong to a case and must not be a canary. If one is found, the new instance joins that case and is marked as deduplicated. The setting is read in `src/dispatch/config.py` (lines 95–96) with `cast=int` and a default of 45. I did not run anything to confirm the behavior at runtime.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py