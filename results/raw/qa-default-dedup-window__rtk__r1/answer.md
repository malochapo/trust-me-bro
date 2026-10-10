When a signal has no filters, a new instance is deduplicated into the most recent case from the same signal. The match must be a non-canary instance created within the default window, and it must already be attached to a case. The window is 45 minutes. The docstring of `filter_signal` in `signal/service.py` says "1-hour window", but the code uses the setting's 45-minute default.

An operator can change it by setting the `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` environment variable to a number of minutes. `config.py` reads it with `config(..., cast=int, default=45)`. The grouping code in `signal/service.py` (line 805) multiplies it by 60 to get seconds.

Canary signals skip this deduplication.

VALUE: 45 minutes
SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
FILE: src/dispatch/config.py