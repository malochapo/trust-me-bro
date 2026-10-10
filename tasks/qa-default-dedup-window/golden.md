Signals without filters use the default deduplication in filter_dedup: instances of the same signal created within the window join the most recent case. The window comes from a setting, not the "1-hour" the filter_signal docstring still mentions.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py
